"""
Email service for LMS notifications
"""
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from sqlalchemy.orm import Session
from database import get_db
from smtp_models import SMTPConfig
from cryptography.fernet import Fernet
from smtp_connection import get_smtp_connection

class EmailService:
    def __init__(self):
        # This service now uses database SMTP configuration via smtp_cache
        # No environment variables needed
        pass
    
    def _connect_tls(self, host: str, port: int):
        """Helper method to connect with TLS"""
        server = smtplib.SMTP(host, port, timeout=10)
        server.starttls()
        return server
    
    def send_email(self, to_email: str, subject: str, body: str, is_html: bool = False) -> bool:
        """Send email using the same method as campaigns"""
        try:
            # Use the same SMTP cache as campaigns
            from smtp_cache import smtp_cache
            smtp_config = smtp_cache.get_smtp_config()
            
            if not smtp_config:
                print("Email send failed: No active SMTP configuration found")
                return False
            
            print(f"Using cached SMTP config: {smtp_config['smtp_host']}:{smtp_config['smtp_port']}")
            
            # Create email message using EmailMessage (same as campaigns)
            from email.message import EmailMessage
            message = EmailMessage()
            message["From"] = f"{smtp_config['smtp_from_name']} <{smtp_config['smtp_from_email']}>"
            message["To"] = to_email
            message["Subject"] = subject
            message.set_content(body, subtype="html" if is_html else "plain")
            
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
                print(f"Email send failed for {to_email}: {error}")
                return False
                
            try:
                server.send_message(message)
            except Exception as e:
                print(f"Email send failed for {to_email}: {str(e)}")
                return False
            finally:
                if server:
                    try:
                        server.quit()
                    except:
                        pass
            
            print(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            print(f"Email send failed: {str(e)}")
            return False
    
    def send_welcome_email(self, user_email: str, username: str, password: str) -> bool:
        """Send welcome email to new user"""
        subject = "Welcome to LMS"
        body = f"""
        <h2>Welcome to Learning Management System!</h2>
        <p>Hello {username},</p>
        <p>Your account has been created successfully. Here are your login credentials:</p>
        <ul>
            <li><strong>Username:</strong> {username}</li>
            <li><strong>Password:</strong> {password}</li>
        </ul>
        <p>Please login at: <a href="http://localhost:3000/login">http://localhost:3000/login</a></p>
        <p>We recommend changing your password after first login.</p>
        <br>
        <p>Best regards,<br>LMS Team</p>
        """
        return self.send_email(user_email, subject, body, is_html=True)
    
    def send_course_enrollment_email(self, user_email: str, username: str, course_title: str) -> bool:
        """Send course enrollment confirmation"""
        subject = f"Enrolled in {course_title}"
        body = f"""
        <h2>Course Enrollment Confirmation</h2>
        <p>Hello {username},</p>
        <p>You have successfully enrolled in: <strong>{course_title}</strong></p>
        <p>Access your courses at: <a href="http://localhost:3000/student/dashboard">Student Dashboard</a></p>
        <br>
        <p>Happy learning!<br>LMS Team</p>
        """
        return self.send_email(user_email, subject, body, is_html=True)
    
    def send_cohort_welcome_email(self, user_email: str, username: str, cohort_name: str, start_date: str, instructor_name: str, db: Session = None) -> bool:
        """Send cohort welcome email using database template or default"""
        try:
            # Try to get template from database
            if db:
                from database import EmailTemplate
                template = db.query(EmailTemplate).filter(
                    EmailTemplate.name == "Cohort Welcome Email",
                    EmailTemplate.is_active == True
                ).first()
                
                if template:
                    # Use database template
                    subject = template.subject.format(
                        username=username,
                        cohort_name=cohort_name,
                        start_date=start_date,
                        instructor_name=instructor_name
                    )
                    body = template.body.format(
                        username=username,
                        cohort_name=cohort_name,
                        start_date=start_date,
                        instructor_name=instructor_name,
                        email=user_email
                    )
                    return self.send_email(user_email, subject, body, is_html=False)
        except Exception as e:
            print(f"Failed to use database template: {str(e)}")
        
        # Fallback to default template
        subject = "Welcome to Kamba LMS - Your Learning Journey Begins!"
        body = f"""
Dear {username},

Welcome to Kamba LMS! We're excited to have you join our learning community.

Your cohort details:
- Cohort Name: {cohort_name}
- Start Date: {start_date}
- Instructor: {instructor_name}

What's next:
1. Complete your profile setup
2. Explore your course materials
3. Join your first session
4. Connect with your peers

If you have any questions, don't hesitate to reach out to our support team.

Best regards,
The Kamba LMS Team

---
This is an automated message. Please do not reply to this email.
        """
        return self.send_email(user_email, subject, body, is_html=False)

# Global email service instance
email_service = EmailService()