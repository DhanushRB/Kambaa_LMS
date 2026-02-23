
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, EmailTemplate, Admin
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def sync_feedback_template():
    print("Syncing Feedback Templates...")
    
    templates = [
        {
            "name": "Feedback Submission Confirmation",
            "subject": "Thank You for Your Feedback: {feedback_title}",
            "body": """
Dear {username},

Thank you for providing your feedback on "{feedback_title}". Your input is valuable to us and helps us improve the learning experience.

Submission Details:
- Title: {feedback_title}
- Session: {session_title}
- Date: {submitted_at}

We appreciate your time and effort in sharing your thoughts with us.

Best regards,
The Kamba LMS Team

---
This is an automated message. Please do not reply to this email.
            """.strip(),
            "target_role": "Student",
            "category": "notification",
        },
        {
            "name": "Feedback Request Notification",
            "subject": "New Feedback Form: {feedback_title}",
            "body": """
Dear {username},

A new feedback form "{feedback_title}" has been created for the session "{session_title}".

We value your input and would appreciate it if you could take a moment to provide your feedback.

You can find the feedback form in your course dashboard under the session details.

Best regards,
The Kamba LMS Team

---
This is an automated message. Please do not reply to this email.
            """.strip(),
            "target_role": "Student",
            "category": "notification",
        }
    ]
    
    # Get an admin ID for created_by
    admin = db.query(Admin).first()
    admin_id = admin.id if admin else 1

    for config in templates:
        print(f"Syncing template: {config['name']}...")
        existing = db.query(EmailTemplate).filter(EmailTemplate.name == config["name"]).first()

        if not existing:
            new_template = EmailTemplate(
                name=config["name"],
                subject=config["subject"],
                body=config["body"],
                target_role=config["target_role"],
                category=config["category"],
                is_active=True,
                created_by=admin_id
            )
            db.add(new_template)
            print(f"Template '{config['name']}' created successfully!")
        else:
            print(f"Template '{config['name']}' already exists. Updating content...")
            existing.subject = config["subject"]
            existing.body = config["body"]
            print(f"Template '{config['name']}' updated successfully!")
    
    db.commit()

if __name__ == "__main__":
    sync_feedback_template()
    db.close()

if __name__ == "__main__":
    sync_feedback_template()
    db.close()
