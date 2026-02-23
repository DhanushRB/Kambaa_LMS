import os
import logging
import smtplib
from email.message import EmailMessage
from typing import Iterable, Optional, Dict
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
from database import Notification, EmailLog, NotificationPreference
from smtp_models import SMTPConfig
from smtp_endpoints import decrypt_password
from smtp_cache import smtp_cache
from smtp_connection import get_smtp_connection
from email_styling import wrap_in_base_layout

logger = logging.getLogger(__name__)


class NotificationService:
    """Centralized notification helper for in-app and email delivery."""

    def __init__(self, db: Session):
        self.db = db

    # Preferences -----------------------------------------------------------------
    def _get_preferences(self, user_id: int) -> NotificationPreference:
        prefs = (
            self.db.query(NotificationPreference)
            .filter(NotificationPreference.user_id == user_id)
            .first()
        )
        if not prefs:
            prefs = NotificationPreference(user_id=user_id)
            self.db.add(prefs)
            self.db.commit()
            self.db.refresh(prefs)
        return prefs

    def update_preferences(
        self, user_id: int, email_enabled: Optional[bool], in_app_enabled: Optional[bool]
    ) -> NotificationPreference:
        prefs = self._get_preferences(user_id)
        if email_enabled is not None:
            prefs.email_enabled = email_enabled
        if in_app_enabled is not None:
            prefs.in_app_enabled = in_app_enabled
        self.db.commit()
        self.db.refresh(prefs)
        return prefs

    # In-app notifications --------------------------------------------------------
    def send_in_app_notification(
        self,
        user_id: int,
        title: str,
        message: str,
        notification_type: str = "info",
        action_url: Optional[str] = None,
    ) -> Optional[Notification]:
        prefs = self._get_preferences(user_id)
        if not prefs.in_app_enabled:
            logger.info("In-app notifications disabled for user %s", user_id)
            return None

        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=notification_type,
            action_url=action_url,
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    # Email notifications ---------------------------------------------------------
    def send_email_notification(
        self,
        user_id: Optional[int],
        email: str,
        subject: str,
        body: str,
        background_tasks: Optional[BackgroundTasks] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> EmailLog:
        prefs = self._get_preferences(user_id) if user_id else None
        if prefs and not prefs.email_enabled:
            logger.info("Email notifications disabled for user %s", user_id)
            return EmailLog(
                user_id=user_id,
                email=email,
                subject=subject,
                status="skipped",
            )

        if background_tasks is not None:
            background_tasks.add_task(
                self._dispatch_email,
                email,
                subject,
                body,
                headers or {},
                user_id,
            )
            status = "queued"
            error_message = None
        else:
            status, error_message = self._dispatch_email(
                email, subject, body, headers or {}, user_id
            )

        email_log = EmailLog(
            user_id=user_id,
            email=email,
            subject=subject,
            status=status,
            error_message=error_message,
        )
        self.db.add(email_log)
        self.db.commit()
        self.db.refresh(email_log)
        return email_log

    def _get_smtp_config(self) -> Optional[Dict[str, str]]:
        """Get cached SMTP configuration"""
        return smtp_cache.get_smtp_config()

    def _dispatch_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        headers: Dict[str, str],
        user_id: Optional[int],
    ):
        # Get cached SMTP config
        smtp_config = self._get_smtp_config()
        if not smtp_config:
            logger.error("No active SMTP configuration found; cannot send email")
            return "failed", "No active SMTP configuration found"

        try:
            message = EmailMessage()
            message["From"] = f"{smtp_config['smtp_from_name']} <{smtp_config['smtp_from_email']}>"
            message["To"] = to_email
            message["Subject"] = subject
            for key, value in headers.items():
                message[key] = value
                
            # Wrap body in professional layout if it's not already HTML
            styled_body = wrap_in_base_layout(body, subject)
            message.set_content(styled_body, subtype="html")

            # Use robust connection utility
            server, error = get_smtp_connection(
                host=smtp_config['smtp_host'],
                port=smtp_config['smtp_port'],
                username=smtp_config['smtp_username'],
                password=smtp_config['smtp_password'],
                use_tls=smtp_config['use_tls'],
                use_ssl=smtp_config['use_ssl'],
                timeout=30
            )
            
            if error:
                logger.error(f"SMTP connection error for {to_email}: {error}")
                return "failed", error
                
            try:
                server.send_message(message)
            except Exception as e:
                logger.error(f"SMTP send error for {to_email}: {str(e)}")
                return "failed", str(e)
            finally:
                if server:
                    try:
                        server.quit()
                    except:
                        pass
                    
            logger.info("Email sent to %s (user_id=%s)", to_email, user_id)
            return "sent", None
        except smtplib.SMTPAuthenticationError as exc:
            error_msg = f"SMTP authentication failed: {str(exc)}"
            logger.error("Email send failed: %s", error_msg)
            # Invalidate cache on auth failure to force refresh
            smtp_cache.invalidate_cache()
            return "failed", error_msg
        except smtplib.SMTPConnectError as exc:
            error_msg = f"Failed to connect to SMTP server: {str(exc)}"
            logger.error("Email send failed: %s", error_msg)
            return "failed", error_msg
        except smtplib.SMTPException as exc:
            error_msg = f"SMTP error: {str(exc)}"
            logger.error("Email send failed: %s", error_msg)
            return "failed", error_msg
        except Exception as exc:
            error_msg = f"Unexpected error: {type(exc).__name__}: {str(exc)}"
            logger.error("Email send failed: %s", error_msg)
            return "failed", error_msg

    # Bulk helper -----------------------------------------------------------------
    def send_bulk_notifications(
        self,
        user_ids: Iterable[int],
        title: str,
        message: str,
        notification_type: str = "info",
        action_url: Optional[str] = None,
    ):
        created = []
        for uid in user_ids:
            created.append(
                self.send_in_app_notification(
                    user_id=uid,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    action_url=action_url,
                )
            )
        return created

    def send_email_notification_sync(
        self,
        user_id: Optional[int],
        email: str,
        subject: str,
        body: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> str:
        """Synchronous email sending for scheduled campaigns"""
        prefs = self._get_preferences(user_id) if user_id else None
        if prefs and not prefs.email_enabled:
            logger.info("Email notifications disabled for user %s", user_id)
            return "skipped"

        status, error_message = self._dispatch_email(
            email, subject, body, headers or {}, user_id
        )

        # Log to database
        email_log = EmailLog(
            user_id=user_id,
            email=email,
            subject=subject,
            status=status,
            error_message=error_message,
        )
        self.db.add(email_log)
        self.db.commit()
        
        return status


def render_template(template_str: str, context: Dict[str, str]) -> str:
    """Simple placeholder renderer for HTML templates."""
    try:
        return template_str.format(**context)
    except KeyError as exc:
        missing = exc.args[0]
        logger.warning("Missing placeholder in context: %s", missing)
        return template_str
