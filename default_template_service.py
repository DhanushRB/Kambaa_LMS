from sqlalchemy.orm import Session
from database import EmailTemplate
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class DefaultTemplateService:
    """Service to manage and use default email templates"""
    
    @staticmethod
    def get_cohort_welcome_template(db: Session) -> Optional[EmailTemplate]:
        """Get the cohort welcome email template"""
        try:
            template = db.query(EmailTemplate).filter(
                EmailTemplate.name == "Cohort Welcome Email"
            ).first()
            return template
        except Exception as e:
            logger.error(f"Error getting cohort welcome template: {str(e)}")
            return None
    
    @staticmethod
    def format_cohort_welcome_email(template: EmailTemplate, user_data: Dict[str, Any]) -> Dict[str, str]:
        """Format cohort welcome email with user data"""
        try:
            subject = template.subject.format(
                username=user_data.get('username', ''),
                cohort_name=user_data.get('cohort_name', ''),
                start_date=user_data.get('start_date', ''),
                instructor_name=user_data.get('instructor_name', '')
            )
            
            body = template.body.format(
                username=user_data.get('username', ''),
                cohort_name=user_data.get('cohort_name', ''),
                start_date=user_data.get('start_date', ''),
                instructor_name=user_data.get('instructor_name', ''),
                email=user_data.get('email', '')
            )
            
            return {
                "subject": subject,
                "body": body
            }
        except Exception as e:
            logger.error(f"Error formatting cohort welcome email: {str(e)}")
            return {
                "subject": template.subject,
                "body": template.body
            }
    

    
    @staticmethod
    def send_cohort_welcome_email(db: Session, user_data: Dict[str, Any], email_service) -> bool:
        """Send cohort welcome email using default template"""
        try:
            template = DefaultTemplateService.get_cohort_welcome_template(db)
            if not template:
                logger.warning("Cohort welcome template not found, using fallback")
                return False
            
            formatted_email = DefaultTemplateService.format_cohort_welcome_email(template, user_data)
            
            # Use the email service to send the email
            success = email_service.send_email(
                to_email=user_data.get('email'),
                subject=formatted_email['subject'],
                body=formatted_email['body']
            )
            
            return success
        except Exception as e:
            logger.error(f"Error sending cohort welcome email: {str(e)}")
            return False
    

    
    @staticmethod
    def initialize_default_templates(db: Session, admin_id: int) -> bool:
        """Initialize default templates if they don't exist"""
        try:
            from default_email_templates import DEFAULT_TEMPLATES
            
            created_count = 0
            for template_key, template_config in DEFAULT_TEMPLATES.items():
                # Check if template already exists
                existing_template = db.query(EmailTemplate).filter(
                    EmailTemplate.name == template_config["name"]
                ).first()
                
                if not existing_template:
                    template = EmailTemplate(
                        name=template_config["name"],
                        subject=template_config["subject"],
                        body=template_config["body"],
                        target_role=template_config["target_role"],
                        category=template_config["category"],
                        is_active=True,
                        created_by=admin_id
                    )
                    db.add(template)
                    created_count += 1
            
            if created_count > 0:
                db.commit()
                logger.info(f"Initialized {created_count} default email templates")
            
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error initializing default templates: {str(e)}")
            return False