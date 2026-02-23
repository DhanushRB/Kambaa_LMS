from database import SessionLocal, EmailTemplate, Admin
from sqlalchemy.orm import Session

db = SessionLocal()

def sync_assignment_reminder_template():
    print("Syncing Assignment Due Reminder template...")
    
    config = {
        "name": "Assignment Due Reminder",
        "subject": "Reminder: Assignment '{assignment_title}' is due tomorrow",
        "body": """
Dear {username},

This is a friendly reminder that the assignment "{assignment_title}" for session "{session_title}" is due in 24 hours.

Our records show that you have not yet submitted this assignment. Please ensure you complete and submit it before the deadline to avoid any marks deduction.

Due Date: {due_date}

Best regards,
The Kamba LMS Team

---
This is an automated message. Please do not reply to this email.
        """.strip(),
        "target_role": "Student",
        "category": "notification",
    }
    
    # Get an admin ID for created_by
    admin = db.query(Admin).first()
    admin_id = admin.id if admin else 1

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
    sync_assignment_reminder_template()
    db.close()
