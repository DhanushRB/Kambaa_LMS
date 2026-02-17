"""
Enhanced Email Service using Database SMTP Configuration
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
import os
from jinja2 import Template

from database import SessionLocal
from smtp_models import SMTPConfig

logger = logging.getLogger(__name__)

# Encryption key for SMTP passwords
ENCRYPTION_KEY = os.getenv("SMTP_ENCRYPTION_KEY", Fernet.generate_key())
if isinstance(ENCRYPTION_KEY, str):
    ENCRYPTION_KEY = ENCRYPTION_KEY.encode()
cipher_suite = Fernet(ENCRYPTION_KEY)

class EmailService:
    def __init__(self):
        self.db = SessionLocal()
        self.smtp_config = None
        self._load_smtp_config()
    
    def _load_smtp_config(self):
        """Load active SMTP configuration from database"""
        try:
            # Always get fresh config from database
            self.smtp_config = self.db.query(SMTPConfig).filter(SMTPConfig.is_active == True).first()
            if self.smtp_config:
                logger.info(f"SMTP configuration loaded: {self.smtp_config.smtp_host}:{self.smtp_config.smtp_port}")
            else:
                logger.warning("No active SMTP configuration found in database")
        except Exception as e:
            logger.error(f"Failed to load SMTP config: {str(e)}")
            self.smtp_config = None
    
    def _refresh_config(self):
        """Refresh SMTP configuration from database"""
        self._load_smtp_config()
    
    def _decrypt_password(self, encrypted_password: str) -> str:
        """Decrypt SMTP password"""
        return cipher_suite.decrypt(encrypted_password.encode()).decode()
    
    def is_configured(self) -> bool:
        """Check if SMTP is properly configured"""
        return self.smtp_config is not None
    
    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None
    ) -> bool:
        """
        Send email using configured SMTP settings
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            body: Plain text body
            html_body: HTML body (optional)
            attachments: List of attachments with 'filename' and 'content' keys
            cc_emails: List of CC email addresses
            bcc_emails: List of BCC email addresses
        
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        # Always refresh config before sending to get latest settings
        self._refresh_config()
        
        if not self.is_configured():
            logger.error("SMTP not configured. Cannot send email. Please configure SMTP settings in admin panel.")
            return False
        
        try:
            # Decrypt password
            password = self._decrypt_password(self.smtp_config.smtp_password)
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.smtp_config.smtp_from_name} <{self.smtp_config.smtp_from_email}>"
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            # Add body parts
            if body:
                msg.attach(MIMEText(body, 'plain'))
            
            if html_body:
                msg.attach(MIMEText(html_body, 'html'))
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment['content'])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment["filename"]}'
                    )
                    msg.attach(part)
            
            # Prepare recipient list
            all_recipients = to_emails.copy()
            if cc_emails:
                all_recipients.extend(cc_emails)
            if bcc_emails:
                all_recipients.extend(bcc_emails)
            
            # Send email with proper connection handling
            server = None
            try:
                if self.smtp_config.use_ssl or self.smtp_config.smtp_port == 465:
                    server = smtplib.SMTP_SSL(self.smtp_config.smtp_host, self.smtp_config.smtp_port, timeout=30)
                else:
                    server = smtplib.SMTP(self.smtp_config.smtp_host, self.smtp_config.smtp_port, timeout=30)
                    if self.smtp_config.use_tls:
                        server.starttls()
                
                server.login(self.smtp_config.smtp_username, password)
                server.send_message(msg, to_addrs=all_recipients)
                
                logger.info(f"Email sent successfully to {len(all_recipients)} recipients using SMTP: {self.smtp_config.smtp_host}:{self.smtp_config.smtp_port}")
                return True
                
            except Exception as smtp_error:
                logger.error(f"SMTP connection/send error: {str(smtp_error)}")
                raise smtp_error
            finally:
                if server:
                    try:
                        server.quit()
                    except:
                        pass
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False
    
    def send_template_email(
        self,
        to_emails: List[str],
        template_name: str,
        template_data: Dict[str, Any],
        subject: str
    ) -> bool:
        """
        Send email using predefined templates
        
        Args:
            to_emails: List of recipient email addresses
            template_name: Name of the email template
            template_data: Data to populate the template
            subject: Email subject
        
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        templates = {
            'welcome': {
                'subject': 'Welcome to Kambaa AI LMS',
                'html': '''
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h2 style="color: #f59e0b;">Welcome to Kambaa AI LMS!</h2>
                        <p>Hello {{ name }},</p>
                        <p>Welcome to our Learning Management System. Your account has been created successfully.</p>
                        <div style="background: #f8fafc; padding: 15px; border-radius: 5px; margin: 20px 0;">
                            <strong>Account Details:</strong><br>
                            Username: {{ username }}<br>
                            Email: {{ email }}<br>
                            Role: {{ role }}
                        </div>
                        <p>You can now log in to access your courses and resources.</p>
                        <p>Best regards,<br>Kambaa AI LMS Team</p>
                    </div>
                </body>
                </html>
                ''',
                'text': '''
                Welcome to Kambaa AI LMS!
                
                Hello {{ name }},
                
                Welcome to our Learning Management System. Your account has been created successfully.
                
                Account Details:
                Username: {{ username }}
                Email: {{ email }}
                Role: {{ role }}
                
                You can now log in to access your courses and resources.
                
                Best regards,
                Kambaa AI LMS Team
                '''
            },
            'course_enrollment': {
                'subject': 'Course Enrollment Confirmation',
                'html': '''
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h2 style="color: #f59e0b;">Course Enrollment Confirmation</h2>
                        <p>Hello {{ student_name }},</p>
                        <p>You have been successfully enrolled in the following course:</p>
                        <div style="background: #f0fdf4; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #10b981;">
                            <strong>{{ course_title }}</strong><br>
                            {{ course_description }}
                        </div>
                        <p>You can now access the course materials and start your learning journey.</p>
                        <p>Best regards,<br>Kambaa AI LMS Team</p>
                    </div>
                </body>
                </html>
                ''',
                'text': '''
                Course Enrollment Confirmation
                
                Hello {{ student_name }},
                
                You have been successfully enrolled in the following course:
                
                {{ course_title }}
                {{ course_description }}
                
                You can now access the course materials and start your learning journey.
                
                Best regards,
                Kambaa AI LMS Team
                '''
            },
            'assignment_reminder': {
                'subject': 'Assignment Due Reminder',
                'html': '''
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h2 style="color: #f59e0b;">Assignment Due Reminder</h2>
                        <p>Hello {{ student_name }},</p>
                        <p>This is a reminder that you have an assignment due soon:</p>
                        <div style="background: #fef3c7; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #f59e0b;">
                            <strong>{{ assignment_title }}</strong><br>
                            Course: {{ course_title }}<br>
                            Due Date: {{ due_date }}
                        </div>
                        <p>Please make sure to submit your assignment before the deadline.</p>
                        <p>Best regards,<br>Kambaa AI LMS Team</p>
                    </div>
                </body>
                </html>
                ''',
                'text': '''
                Assignment Due Reminder
                
                Hello {{ student_name }},
                
                This is a reminder that you have an assignment due soon:
                
                {{ assignment_title }}
                Course: {{ course_title }}
                Due Date: {{ due_date }}
                
                Please make sure to submit your assignment before the deadline.
                
                Best regards,
                Kambaa AI LMS Team
                '''
            },
            'session_reminder': {
                'subject': 'Upcoming Session Reminder',
                'html': '''
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h2 style="color: #f59e0b;">Upcoming Session Reminder</h2>
                        <p>Hello {{ student_name }},</p>
                        <p>You have an upcoming session:</p>
                        <div style="background: #dbeafe; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #3b82f6;">
                            <strong>{{ session_title }}</strong><br>
                            Course: {{ course_title }}<br>
                            Date & Time: {{ session_time }}<br>
                            {% if meeting_link %}
                            <a href="{{ meeting_link }}" style="color: #3b82f6;">Join Meeting</a>
                            {% endif %}
                        </div>
                        <p>Don't forget to attend the session!</p>
                        <p>Best regards,<br>Kambaa AI LMS Team</p>
                    </div>
                </body>
                </html>
                ''',
                'text': '''
                Upcoming Session Reminder
                
                Hello {{ student_name }},
                
                You have an upcoming session:
                
                {{ session_title }}
                Course: {{ course_title }}
                Date & Time: {{ session_time }}
                {% if meeting_link %}
                Meeting Link: {{ meeting_link }}
                {% endif %}
                
                Don't forget to attend the session!
                
                Best regards,
                Kambaa AI LMS Team
                '''
            }
        }
        
        if template_name not in templates:
            logger.error(f"Template '{template_name}' not found")
            return False
        
        template = templates[template_name]
        
        # Render templates
        html_template = Template(template['html'])
        text_template = Template(template['text'])
        
        html_body = html_template.render(**template_data)
        text_body = text_template.render(**template_data)
        
        # Use provided subject or template default
        email_subject = subject or template['subject']
        
        return self.send_email(
            to_emails=to_emails,
            subject=email_subject,
            body=text_body,
            html_body=html_body
        )
    
    def send_bulk_email(
        self,
        recipients: List[Dict[str, Any]],
        subject: str,
        template_name: str,
        common_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send bulk emails with personalized content
        
        Args:
            recipients: List of recipient data with 'email' and template data
            subject: Email subject
            template_name: Name of the email template
            common_data: Common data for all emails
        
        Returns:
            Dict with success/failure counts and details
        """
        results = {
            'total': len(recipients),
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        for recipient in recipients:
            try:
                # Merge common data with recipient-specific data
                template_data = {**(common_data or {}), **recipient}
                
                success = self.send_template_email(
                    to_emails=[recipient['email']],
                    template_name=template_name,
                    template_data=template_data,
                    subject=subject
                )
                
                if success:
                    results['success'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Failed to send to {recipient['email']}")
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"Error sending to {recipient.get('email', 'unknown')}: {str(e)}")
        
        return results
    
    def send_welcome_email(
        self,
        user_email: str,
        username: str,
        password: str = None
    ) -> bool:
        """
        Send welcome email to new user
        
        Args:
            user_email: User's email address
            username: User's username
            password: User's password (optional)
        
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = "Welcome to Kambaa AI LMS"
        
        html_body = f'''
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #f59e0b;">Welcome to Kambaa AI LMS!</h2>
                <p>Hello {username},</p>
                <p>Welcome to our Learning Management System. Your account has been created successfully.</p>
                <div style="background: #f8fafc; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <strong>Account Details:</strong><br>
                    Username: {username}<br>
                    Email: {user_email}<br>
                    {f"Password: {password}<br>" if password else ""}
                </div>
                <p>You can now log in to access your courses and resources.</p>
                <p>Best regards,<br>Kambaa AI LMS Team</p>
            </div>
        </body>
        </html>
        '''
        
        text_body = f'''
        Welcome to Kambaa AI LMS!
        
        Hello {username},
        
        Welcome to our Learning Management System. Your account has been created successfully.
        
        Account Details:
        Username: {username}
        Email: {user_email}
        {f"Password: {password}" if password else ""}
        
        You can now log in to access your courses and resources.
        
        Best regards,
        Kambaa AI LMS Team
        '''
        
        return self.send_email(
            to_emails=[user_email],
            subject=subject,
            body=text_body,
            html_body=html_body
        )
    
    def __del__(self):
        """Close database connection"""
        if hasattr(self, 'db'):
            self.db.close()

# Global email service instance
email_service = EmailService()

def get_email_service() -> EmailService:
    """Get the global email service instance"""
    return email_service

def send_notification_email(
    to_emails: List[str],
    subject: str,
    message: str,
    notification_type: str = "info"
) -> bool:
    """
    Send a simple notification email
    
    Args:
        to_emails: List of recipient email addresses
        subject: Email subject
        message: Email message
        notification_type: Type of notification (info, success, warning, error)
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    # Always get fresh email service instance to ensure latest config
    email_service_instance = EmailService()
    
    colors = {
        'info': '#3b82f6',
        'success': '#10b981',
        'warning': '#f59e0b',
        'error': '#ef4444'
    }
    
    color = colors.get(notification_type, '#3b82f6')
    
    html_body = f'''
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: {color}; color: white; padding: 15px; border-radius: 5px 5px 0 0;">
                <h2 style="margin: 0;">{subject}</h2>
            </div>
            <div style="background: #f8fafc; padding: 20px; border-radius: 0 0 5px 5px; border: 1px solid #e5e7eb;">
                <p>{message}</p>
            </div>
            <p style="margin-top: 20px; font-size: 12px; color: #64748b;">
                This email was sent from Kambaa AI LMS
            </p>
        </div>
    </body>
    </html>
    '''
    
    return email_service_instance.send_email(
        to_emails=to_emails,
        subject=subject,
        body=message,
        html_body=html_body
    )