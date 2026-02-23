from sqlalchemy.orm import Session
from database import SessionLocal, EmailTemplate
from default_email_templates import DEFAULT_TEMPLATES
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sync_all_templates():
    db = SessionLocal()
    try:
        updated_count = 0
        created_count = 0
        
        for key, template_data in DEFAULT_TEMPLATES.items():
            # Find template by name
            template = db.query(EmailTemplate).filter(EmailTemplate.name == template_data["name"]).first()
            
            if template:
                # Update existing template
                template.subject = template_data["subject"]
                template.body = template_data["body"]
                template.target_role = template_data["target_role"]
                template.category = template_data["category"]
                template.is_active = template_data["is_enabled"]
                updated_count += 1
                logger.info(f"Updated template: {template_data['name']}")
            else:
                # Create new template
                new_template = EmailTemplate(
                    name=template_data["name"],
                    subject=template_data["subject"],
                    body=template_data["body"],
                    target_role=template_data["target_role"],
                    category=template_data["category"],
                    is_active=template_data["is_enabled"]
                )
                db.add(new_template)
                created_count += 1
                logger.info(f"Created template: {template_data['name']}")
        
        db.commit()
        logger.info(f"Sync complete. Updated: {updated_count}, Created: {created_count}")
        
    except Exception as e:
        logger.error(f"Sync failed: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    sync_all_templates()
