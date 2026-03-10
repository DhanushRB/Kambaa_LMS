import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, List
from smtp_connection import get_smtp_connection
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
from database import Notification, EmailLog, NotificationPreference, User
from email_templates import (
    get_welcome_email_template,
    get_course_enrollment_template,
    get_assignment_notification_template,
    get_session_reminder_template,
    get_certificate_template
)

from smtp_cache import smtp_cache

logger = logging.getLogger(__name__)

class EmailService:
    """Enhanced email service with template support"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def _get_user_preferences(self, user_id: int) -> NotificationPreference:
        """Get user notification preferences"""
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
    
    def send_welcome_email(self, user_id: int, background_tasks: Optional[BackgroundTasks] = None):
        """Send welcome email to new user"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User {user_id} not found for welcome email")
            return
        
        template = get_welcome_email_template()
        subject = "Welcome to Kambaa AI LMS!"
        
        context = {
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "login_url": "http://localhost:3000/login"
        }
        
        html_content = template.format(**context)
        
        return self._send_email(
            user_id=user_id,
            to_email=user.email,
            subject=subject,
            html_content=html_content,
            background_tasks=background_tasks
        )
    
    def send_course_enrollment_email(self, user_id: int, course_title: str, course_description: str, background_tasks: Optional[BackgroundTasks] = None):
        """Send course enrollment confirmation email"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        
        template = get_course_enrollment_template()
        subject = f"Enrolled in {course_title}"
        
        context = {
            "username": user.username,
            "course_title": course_title,
            "course_description": course_description
        }
        
        html_content = template.format(**context)
        
        return self._send_email(
            user_id=user_id,
            to_email=user.email,
            subject=subject,
            html_content=html_content,
            background_tasks=background_tasks
        )
    
    def send_assignment_notification(self, user_id: int, assignment_title: str, assignment_description: str, due_date: str, background_tasks: Optional[BackgroundTasks] = None):
        """Send assignment notification email"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        
        template = get_assignment_notification_template()
        subject = f"New Assignment: {assignment_title}"
        
        context = {
            "username": user.username,
            "assignment_title": assignment_title,
            "assignment_description": assignment_description,
            "due_date": due_date
        }
        
        html_content = template.format(**context)
        
        return self._send_email(
            user_id=user_id,
            to_email=user.email,
            subject=subject,
            html_content=html_content,
            background_tasks=background_tasks
        )
    
    def send_session_reminder(self, user_id: int, session_title: str, course_title: str, session_time: str, duration: int, zoom_link: Optional[str] = None, background_tasks: Optional[BackgroundTasks] = None):
        """Send session reminder email"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        
        template = get_session_reminder_template()
        subject = f"Session Reminder: {session_title}"
        
        zoom_link_html = ""
        if zoom_link:
            zoom_link_html = f'<p><a href="{zoom_link}" class="button">Join Session</a></p>'
        
        context = {
            "username": user.username,
            "session_title": session_title,
            "course_title": course_title,
            "session_time": session_time,
            "duration": duration,
            "zoom_link": zoom_link_html
        }
        
        html_content = template.format(**context)
        
        return self._send_email(
            user_id=user_id,
            to_email=user.email,
            subject=subject,
            html_content=html_content,
            background_tasks=background_tasks
        )
    
    def send_certificate_email(self, user_id: int, course_title: str, background_tasks: Optional[BackgroundTasks] = None):
        """Send certificate completion email"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        
        template = get_certificate_template()
        subject = f"🎉 Certificate Earned: {course_title}"
        
        context = {
            "username": user.username,
            "course_title": course_title
        }
        
        html_content = template.format(**context)
        
        return self._send_email(
            user_id=user_id,
            to_email=user.email,
            subject=subject,
            html_content=html_content,
            background_tasks=background_tasks
        )
    
    def send_bulk_notification(self, user_ids: List[int], subject: str, message: str, background_tasks: Optional[BackgroundTasks] = None):
        """Send bulk notification to multiple users"""
        results = []
        for user_id in user_ids:
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                result = self._send_email(
                    user_id=user_id,
                    to_email=user.email,
                    subject=subject,
                    html_content=f"<p>Hello {user.username},</p><p>{message}</p>",
                    background_tasks=background_tasks
                )
                results.append(result)
        return results
    
    def _send_email(self, user_id: int, to_email: str, subject: str, html_content: str, background_tasks: Optional[BackgroundTasks] = None):
        """Internal method to send email"""
        # Check user preferences
        prefs = self._get_user_preferences(user_id)
        if not prefs.email_enabled:
            logger.info(f"Email notifications disabled for user {user_id}")
            return self._log_email(user_id, to_email, subject, "skipped", "User disabled email notifications")
        
        if background_tasks:
            background_tasks.add_task(
                self._dispatch_email,
                user_id, to_email, subject, html_content
            )
            return self._log_email(user_id, to_email, subject, "queued", None)
        else:
            status, error_message = self._dispatch_email(user_id, to_email, subject, html_content)
            return self._log_email(user_id, to_email, subject, status, error_message)
    
    def _dispatch_email(self, user_id: int, to_email: str, subject: str, html_content: str):
        """Actually send the email"""
        # Get cached SMTP config
        smtp_config = smtp_cache.get_smtp_config()
        if not smtp_config:
            logger.error("No active SMTP configuration found in database")
            return "failed", "SMTP configuration missing in database"
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{smtp_config['smtp_from_name']} <{smtp_config['smtp_from_email']}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
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
                logger.error(f"Email dispatch error for {to_email}: {error}")
                return "failed", error
                
            try:
                server.send_message(msg)
            except Exception as e:
                logger.error(f"Email dispatch error for {to_email}: {str(e)}")
                return "failed", str(e)
            # removed server.quit() to reuse connection
            
            logger.info(f"Email sent successfully to {to_email}")
            return "sent", None
            
        except Exception as e:
            logger.error(f"Email dispatch error: {str(e)}")
            return "failed", str(e)
    
    def _log_email(self, user_id: int, to_email: str, subject: str, status: str, error_message: str = None):
        """Log email attempt to database"""
        try:
            email_log = EmailLog(
                user_id=user_id,
                email=to_email,
                subject=subject,
                status=status,
                error_message=error_message
            )
            self.db.add(email_log)
            self.db.commit()
            self.db.refresh(email_log)
            return email_log
        except Exception as e:
            logger.error(f"Failed to log email: {str(e)}")
            return None
    
    def test_smtp_connection(self):
        """Test SMTP connection using database configuration"""
        try:
            # Get cached SMTP config
            smtp_config = smtp_cache.get_smtp_config()
            if not smtp_config:
                return False, "No active SMTP configuration found in database"
                
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
                return False, f"SMTP connection failed: {error}"
            
            if server:
                server.quit()
            return True, "SMTP connection successful"
        except Exception as e:
            return False, f"SMTP connection failed: {str(e)}"