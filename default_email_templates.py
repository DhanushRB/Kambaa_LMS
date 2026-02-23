from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from database import get_db, EmailTemplate
from auth import get_current_admin_or_presenter
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/default-templates", tags=["default-templates"])

# HTML Base Layout for Professional Emails
BASE_HTML_LAYOUT = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{subject}}</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f4f7f9; }
        .container { max-width: 600px; margin: 20px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .header { background-color: #f59e0b; padding: 30px; text-align: center; color: white; }
        .header h1 { margin: 0; font-size: 24px; font-weight: 600; }
        .content { padding: 30px; }
        .content p { margin-bottom: 20px; font-size: 16px; }
        .details-box { background-color: #f8fafc; border-left: 4px solid #f59e0b; padding: 20px; margin: 20px 0; border-radius: 4px; }
        .details-box strong { color: #1e293b; }
        .footer { background-color: #f1f5f9; padding: 20px; text-align: center; color: #64748b; font-size: 13px; border-top: 1px solid #e2e8f0; }
        .button { display: inline-block; padding: 12px 24px; background-color: #f59e0b; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 10px; }
        .divider { height: 1px; background-color: #e2e8f0; margin: 25px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Kamba LMS</h1>
        </div>
        <div class="content">
            {{body_content}}
        </div>
        <div class="footer">
            <p>&copy; 2026 Kamba AI LMS. All rights reserved.</p>
            <p>This is an automated message. Please do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
""".strip()

def format_html_template(body_content: str):
    return BASE_HTML_LAYOUT.replace("{{body_content}}", body_content)

# Default template configurations
DEFAULT_TEMPLATES = {
    "cohort_welcome": {
        "name": "Cohort Welcome Email",
        "subject": "Welcome to Kamba LMS - Your Learning Journey Begins!",
        "body": format_html_template("""
            <p>Dear <strong>{username}</strong>,</p>
            <p>Welcome to <strong>Kamba LMS</strong>! We're excited to have you join our learning community. Your cohort details are finalized and ready.</p>
            
            <div class="details-box">
                <p><strong>Cohort Details:</strong></p>
                <p>&bull; <strong>Cohort Name:</strong> {cohort_name}</p>
                <p>&bull; <strong>Start Date:</strong> {start_date}</p>
                <p>&bull; <strong>Instructor:</strong> {instructor_name}</p>
            </div>
            
            <p><strong>What's next:</strong></p>
            <ol>
                <li>Complete your profile setup</li>
                <li>Explore your course materials</li>
                <li>Join your first session</li>
                <li>Connect with your peers</li>
            </ol>
            
            <p>If you have any questions, don't hesitate to reach out to our support team.</p>
            <p>Best regards,<br><strong>The Kamba LMS Team</strong></p>
        """).strip(),
        "target_role": "Student",
        "category": "welcome",
        "is_default": True,
        "is_enabled": True
    },
    "user_registration": {
        "name": "User Registration Welcome Email",
        "subject": "Welcome to Kamba LMS - Your Account Has Been Created!",
        "body": format_html_template("""
            <p>Dear <strong>{username}</strong>,</p>
            <p>Welcome to <strong>Kamba LMS</strong>! Your account has been successfully created. You can now access our comprehensive learning platform.</p>
            
            <div class="details-box">
                <p><strong>Login Details:</strong></p>
                <p>&bull; <strong>Username:</strong> {username}</p>
                <p>&bull; <strong>Email:</strong> {email}</p>
                <p>&bull; <strong>Password:</strong> {password}</p>
            </div>

            <div class="details-box">
                <p><strong>Institution Details:</strong></p>
                <p>&bull; <strong>College:</strong> {college}</p>
                <p>&bull; <strong>Department:</strong> {department}</p>
                <p>&bull; <strong>Year:</strong> {year}</p>
            </div>
            
            <p style="color: #64748b; font-style: italic;">Please keep these credentials safe and change your password after your first login.</p>
            
            <p><strong>To get started:</strong></p>
            <ul>
                <li>Log in to the LMS portal</li>
                <li>Complete your profile</li>
                <li>Explore available courses</li>
                <li>Join your assigned cohort</li>
            </ul>
            
            <p>Best regards,<br><strong>The Kamba LMS Team</strong></p>
        """).strip(),
        "target_role": "All",
        "category": "registration",
        "is_default": True,
        "is_enabled": True
    },
    "new_resource_added": {
        "name": "New Resource Added Notification",
        "subject": "New Resource Added: {resource_title}",
        "body": format_html_template("""
            <p>Dear <strong>{username}</strong>,</p>
            <p>A new learning resource has been added to your course. Dive in and explore the new content!</p>
            
            <div class="details-box">
                <p><strong>Resource Details:</strong></p>
                <p>&bull; <strong>Title:</strong> {resource_title}</p>
                <p>&bull; <strong>Course:</strong> {course_title}</p>
                <p>&bull; <strong>Module:</strong> {module_title}</p>
                <p>&bull; <strong>Session:</strong> {session_title}</p>
                <p>&bull; <strong>Type:</strong> {resource_type}</p>
                <p>&bull; <strong>Added on:</strong> {added_date}</p>
            </div>
            
            <div class="divider"></div>
            <p><strong>Description:</strong><br>{resource_description}</p>
            
            <p>Log in to your account to access this resource and continue your learning journey.</p>
            
            <p>Best regards,<br><strong>The Kamba LMS Team</strong></p>
        """).strip(),
        "target_role": "Student",
        "category": "notification",
        "is_default": True,
        "is_enabled": True
    },
    "course_added_to_cohort": {
        "name": "New Course Added to Cohort",
        "subject": "New Course Available: {course_title}",
        "body": format_html_template("""
            <p>Dear <strong>{username}</strong>,</p>
            <p>Great news! A new course has been added to your cohort and is now available for enrollment.</p>
            
            <div class="details-box">
                <p><strong>Course Details:</strong></p>
                <p>&bull; <strong>Title:</strong> {course_title}</p>
                <p>&bull; <strong>Duration:</strong> {duration_weeks} weeks</p>
                <p>&bull; <strong>Sessions/Week:</strong> {sessions_per_week}</p>
                <p>&bull; <strong>Cohort:</strong> {cohort_name}</p>
                <p>&bull; <strong>Added on:</strong> {added_date}</p>
            </div>
            
            <p><strong>What's next:</strong></p>
            <ol>
                <li>Log in to your LMS account</li>
                <li>Navigate to your cohort dashboard</li>
                <li>Enroll in the new course</li>
            </ol>
            
            <p>This course has been specifically assigned to your cohort by your instructor. Don't miss out!</p>
            
            <p>Best regards,<br><strong>The Kamba LMS Team</strong></p>
        """).strip(),
        "target_role": "Student",
        "category": "notification",
        "is_default": True,
        "is_enabled": True
    },
    "course_enrollment_confirmation": {
        "name": "Course Enrollment Confirmation",
        "subject": "Enrollment Confirmed: {course_title}",
        "body": format_html_template("""
            <p>Dear <strong>{username}</strong>,</p>
            <p>Congratulations! You have successfully enrolled in the course. We're excited to have you on this learning journey!</p>
            
            <div class="details-box">
                <p><strong>Enrollment Details:</strong></p>
                <p>&bull; <strong>Course Title:</strong> {course_title}</p>
                <p>&bull; <strong>Duration:</strong> {duration_weeks} weeks</p>
                <p>&bull; <strong>Start Date:</strong> {course_start_date}</p>
                <p>&bull; <strong>Enrollment Date:</strong> {enrollment_date}</p>
            </div>
            
            <p><strong>Next steps to follow:</strong></p>
            <ul>
                <li>Access your course materials in the LMS</li>
                <li>Review the course syllabus and schedule</li>
                <li>Join your first session when it begins</li>
            </ul>
            
            <p>Best regards,<br><strong>The Kamba LMS Team</strong></p>
        """).strip(),
        "target_role": "Student",
        "category": "notification",
        "is_default": True,
        "is_enabled": True
    },
    "feedback_submission_confirmation": {
        "name": "Feedback Submission Confirmation",
        "subject": "Thank You for Your Feedback: {feedback_title}",
        "body": format_html_template("""
            <p>Dear <strong>{username}</strong>,</p>
            <p>Thank you for providing your feedback on "<strong>{feedback_title}</strong>". Your input is valuable and helps us improve the learning experience.</p>
            
            <div class="details-box">
                <p><strong>Submission Summary:</strong></p>
                <p>&bull; <strong>Form:</strong> {feedback_title}</p>
                <p>&bull; <strong>Session:</strong> {session_title}</p>
                <p>&bull; <strong>Submitted At:</strong> {submitted_at}</p>
            </div>
            
            <p>We appreciate your time and effort in sharing your thoughts with us.</p>
            
            <p>Best regards,<br><strong>The Kamba LMS Team</strong></p>
        """).strip(),
        "target_role": "Student",
        "category": "notification",
        "is_default": True,
        "is_enabled": True
    },
    "feedback_request_notification": {
        "name": "Feedback Request Notification",
        "subject": "New Feedback Form: {feedback_title}",
        "body": format_html_template("""
            <p>Dear <strong>{username}</strong>,</p>
            <p>A new feedback form "<strong>{feedback_title}</strong>" has been created for your session.</p>
            
            <div class="details-box">
                <p><strong>Session:</strong> {session_title}</p>
            </div>
            
            <p>We value your input and would appreciate it if you could take a moment to provide your feedback. Your anonymous responses help us refine our sessions.</p>
            
            <p>You can find the feedback form in your course dashboard under the session details.</p>
            
            <p>Best regards,<br><strong>The Kamba LMS Team</strong></p>
        """).strip(),
        "target_role": "Student",
        "category": "notification",
        "is_default": True,
        "is_enabled": True
    },
    "assignment_due_reminder": {
        "name": "Assignment Due Reminder",
        "subject": "Reminder: Assignment '{assignment_title}' is due tomorrow",
        "body": format_html_template("""
            <p>Dear <strong>{username}</strong>,</p>
            <p>This is a friendly reminder that the assignment "<strong>{assignment_title}</strong>" is due in <strong>24 hours</strong>.</p>
            
            <div class="details-box">
                <p><strong>Assignment Details:</strong></p>
                <p>&bull; <strong>Title:</strong> {assignment_title}</p>
                <p>&bull; <strong>Session:</strong> {session_title}</p>
                <p>&bull; <strong>Due Date:</strong> {due_date}</p>
            </div>
            
            <p style="color: #ef4444; font-weight: bold;">Our records show that you have not yet submitted this assignment.</p>
            <p>Please ensure you complete and submit it before the deadline to avoid any marks deduction.</p>
            
            <p>Best regards,<br><strong>The Kamba LMS Team</strong></p>
        """).strip(),
        "target_role": "Student",
        "category": "notification",
        "is_default": True,
        "is_enabled": True
    }
}

class DefaultTemplateResponse(BaseModel):
    id: int
    name: str
    subject: str
    body: str
    target_role: str
    category: str
    is_default: bool = True
    is_active: bool

@router.get("/", response_model=List[DefaultTemplateResponse])
async def get_default_templates(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get all default email templates"""
    try:
        # Get all default templates from database
        default_templates = db.query(EmailTemplate).filter(
            EmailTemplate.category.in_(["welcome", "registration", "notification"])
        ).all()
        
        return [
            DefaultTemplateResponse(
                id=template.id,
                name=template.name,
                subject=template.subject,
                body=template.body,
                target_role=template.target_role,
                category=template.category,
                is_default=True,
                is_active=template.is_active
            )
            for template in default_templates
        ]
    except Exception as e:
        logger.error(f"Get default templates error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch default templates")

@router.post("/cleanup-duplicates")
async def cleanup_duplicate_templates(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Remove duplicate default templates, keeping only the first one of each name"""
    try:
        removed_count = 0
        
        # Get all templates grouped by name
        for template_name in [config["name"] for config in DEFAULT_TEMPLATES.values()]:
            templates = db.query(EmailTemplate).filter(
                EmailTemplate.name == template_name
            ).order_by(EmailTemplate.id).all()
            
            # If more than one exists, delete the duplicates (keep the first one)
            if len(templates) > 1:
                for template in templates[1:]:  # Skip the first one
                    db.delete(template)
                    removed_count += 1
        
        if removed_count > 0:
            db.commit()
        
        return {
            "message": f"Removed {removed_count} duplicate templates",
            "removed_count": removed_count
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Cleanup duplicates error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cleanup duplicate templates")

@router.post("/sync")
async def sync_default_templates(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Sync all default templates - create any missing ones"""
    try:
        created_count = 0
        updated_count = 0
        
        for template_key, template_config in DEFAULT_TEMPLATES.items():
            # Check if template already exists
            existing_template = db.query(EmailTemplate).filter(
                EmailTemplate.name == template_config["name"]
            ).first()
            
            if not existing_template:
                # Create new template
                template = EmailTemplate(
                    name=template_config["name"],
                    subject=template_config["subject"],
                    body=template_config["body"],
                    target_role=template_config["target_role"],
                    category=template_config["category"],
                    is_active=True,
                    created_by=current_admin.id
                )
                db.add(template)
                created_count += 1
            else:
                # Ensure template is active
                if not existing_template.is_active:
                    existing_template.is_active = True
                    updated_count += 1
        
        if created_count > 0 or updated_count > 0:
            db.commit()
        
        return {
            "message": "Default templates synchronized successfully",
            "created": created_count,
            "updated": updated_count,
            "total_templates": len(DEFAULT_TEMPLATES)
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Sync default templates error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to sync default templates")

@router.post("/initialize")
async def initialize_default_templates(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Initialize default email templates in the database"""
    try:
        created_templates = await create_default_templates_in_db(db, current_admin.id)
        return {
            "message": f"Successfully initialized {len(created_templates)} default templates",
            "templates": [
                {
                    "id": template.id,
                    "name": template.name,
                    "category": template.category
                }
                for template in created_templates
            ]
        }
    except Exception as e:
        logger.error(f"Initialize default templates error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initialize default templates")

@router.put("/{template_id}")
async def update_default_template(
    template_id: int,
    template_data: dict,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Update a default email template"""
    try:
        template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Update allowed fields
        allowed_fields = ["subject", "body"]
        for field in allowed_fields:
            if field in template_data:
                setattr(template, field, template_data[field])
        
        db.commit()
        db.refresh(template)
        
        return {
            "message": "Default template updated successfully",
            "template": {
                "id": template.id,
                "name": template.name,
                "subject": template.subject,
                "body": template.body,
                "category": template.category
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update default template error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update default template")

@router.put("/{template_id}/toggle")
async def toggle_default_template(
    template_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Toggle default template enabled/disabled state"""
    try:
        template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        template.is_active = not template.is_active
        db.commit()
        db.refresh(template)
        
        return {
            "message": f"Template {'enabled' if template.is_active else 'disabled'} successfully",
            "template_id": template.id,
            "is_active": template.is_active
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Toggle template error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to toggle template")

@router.post("/reset/{template_type}")
async def reset_default_template(
    template_type: str,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Reset a default template to its original content"""
    try:
        if template_type not in DEFAULT_TEMPLATES:
            raise HTTPException(status_code=400, detail="Invalid template type")
        
        # Find the template in database
        template_config = DEFAULT_TEMPLATES[template_type]
        template = db.query(EmailTemplate).filter(
            EmailTemplate.name == template_config["name"]
        ).first()
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Reset to default values
        template.subject = template_config["subject"]
        template.body = template_config["body"]
        
        db.commit()
        db.refresh(template)
        
        return {
            "message": f"Template '{template.name}' reset to default successfully",
            "template": {
                "id": template.id,
                "name": template.name,
                "subject": template.subject,
                "body": template.body
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Reset default template error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reset template")

async def create_default_templates_in_db(db: Session, admin_id: int):
    """Helper function to create default templates in database"""
    created_templates = []
    
    for template_key, template_config in DEFAULT_TEMPLATES.items():
        # Check if template already exists by name
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
            created_templates.append(template)
    
    if created_templates:
        db.commit()
        for template in created_templates:
            db.refresh(template)
    
    return created_templates

@router.get("/cohort-welcome")
async def get_cohort_welcome_template(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get the cohort welcome template for use in cohort creation"""
    try:
        template = db.query(EmailTemplate).filter(
            EmailTemplate.name == "Cohort Welcome Email"
        ).first()
        
        if not template:
            # Create if doesn't exist
            await create_default_templates_in_db(db, current_admin.id)
            template = db.query(EmailTemplate).filter(
                EmailTemplate.name == "Cohort Welcome Email"
            ).first()
        
        return {
            "id": template.id,
            "name": template.name,
            "subject": template.subject,
            "body": template.body,
            "target_role": template.target_role,
            "category": template.category
        }
    except Exception as e:
        logger.error(f"Get cohort welcome template error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get cohort welcome template")

@router.get("/course-added-to-cohort")
async def get_course_added_to_cohort_template(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get the course added to cohort template for use in cohort course assignment"""
    try:
        template = db.query(EmailTemplate).filter(
            EmailTemplate.name == "New Course Added to Cohort"
        ).first()
        
        if not template:
            # Create if doesn't exist
            await create_default_templates_in_db(db, current_admin.id)
            template = db.query(EmailTemplate).filter(
                EmailTemplate.name == "New Course Added to Cohort"
            ).first()
        
        return {
            "id": template.id,
            "name": template.name,
            "subject": template.subject,
            "body": template.body,
            "target_role": template.target_role,
            "category": template.category
        }
    except Exception as e:
        logger.error(f"Get course added to cohort template error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get course added to cohort template")

