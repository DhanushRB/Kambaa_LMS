from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from database import get_db, EmailTemplate
from auth import get_current_admin_or_presenter
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/default-templates", tags=["default-templates"])

# Default template configurations
DEFAULT_TEMPLATES = {
    "cohort_welcome": {
        "name": "Cohort Welcome Email",
        "subject": "Welcome to Kamba LMS - Your Learning Journey Begins!",
        "body": """
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
        """.strip(),
        "target_role": "Student",
        "category": "welcome",
        "is_default": True,
        "is_enabled": True
    },
    "user_registration": {
        "name": "User Registration Welcome Email",
        "subject": "Welcome to Kamba LMS - Your Account Has Been Created!",
        "body": """
Dear {username},

Welcome to Kamba LMS! Your account has been successfully created.

Your login details:
- Username: {username}
- Email: {email}
- Password: {password}
- College: {college}
- Department: {department}
- Year: {year}

Please keep these credentials safe and change your password after your first login.

To get started:
1. Log in to the LMS portal
2. Complete your profile
3. Explore available courses
4. Join your assigned cohort (if applicable)

If you have any questions or need assistance, please contact our support team.

Best regards,
The Kamba LMS Team

---
This is an automated message. Please do not reply to this email.
        """.strip(),
        "target_role": "All",
        "category": "registration",
        "is_default": True,
        "is_enabled": True
    },
    "new_resource_added": {
        "name": "New Resource Added Notification",
        "subject": "New Resource Added: {resource_title}",
        "body": """
Dear {username},

A new resource has been added to your course!

Resource Details:
- Title: {resource_title}
- Course: {course_title}
- Module: {module_title}
- Session: {session_title}
- Type: {resource_type}
- Description: {resource_description}
- Added on: {added_date}

Log in to your LMS account to access this resource and continue your learning journey.

Best regards,
The Kamba LMS Team

---
This is an automated message. Please do not reply to this email.
        """.strip(),
        "target_role": "Student",
        "category": "notification",
        "is_default": True,
        "is_enabled": True
    },
    "course_added_to_cohort": {
        "name": "New Course Added to Cohort",
        "subject": "New Course Available: {course_title}",
        "body": """
Dear {username},

Great news! A new course has been added to your cohort and is now available for enrollment.

Course Details:
- Course Title: {course_title}
- Description: {course_description}
- Duration: {duration_weeks} weeks
- Sessions per Week: {sessions_per_week}
- Cohort: {cohort_name}
- Added on: {added_date}

What's next:
1. Log in to your LMS account
2. Navigate to your cohort dashboard
3. Enroll in the new course
4. Start your learning journey

This course has been specifically assigned to your cohort by your instructor. Don't miss out on this learning opportunity!

Best regards,
The Kamba LMS Team

---
This is an automated message. Please do not reply to this email.
        """.strip(),
        "target_role": "Student",
        "category": "notification",
        "is_default": True,
        "is_enabled": True
    },
    "course_enrollment_confirmation": {
        "name": "Course Enrollment Confirmation",
        "subject": "Enrollment Confirmed: {course_title}",
        "body": """
Dear {username},

Congratulations! You have successfully enrolled in the course.

Enrollment Details:
- Course Title: {course_title}
- Description: {course_description}
- Duration: {duration_weeks} weeks
- Sessions per Week: {sessions_per_week}
- Enrollment Date: {enrollment_date}
- Course Start Date: {course_start_date}

What's next:
1. Access your course materials in the LMS
2. Review the course syllabus and schedule
3. Join your first session when it begins
4. Connect with your instructor and classmates

We're excited to have you on this learning journey! If you have any questions, please don't hesitate to contact our support team.

Best regards,
The Kamba LMS Team

---
This is an automated message. Please do not reply to this email.
        """.strip(),
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

