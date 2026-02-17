from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db, Admin, EmailTemplate, EmailCampaign
from auth import get_current_admin_or_presenter
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/email-templates", tags=["email-templates"])

# Pydantic models
class EmailTemplateCreate(BaseModel):
    name: str
    subject: str
    body: str
    target_role: str = "All"  # Student, Admin, Presenter, All
    category: str = "general"
    is_active: bool = True

class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    target_role: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

@router.get("/")
async def get_email_templates(
    page: int = 1,
    limit: int = 50,
    category: Optional[str] = None,
    target_role: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get all email templates with filtering"""
    try:
        query = db.query(EmailTemplate)
        
        if category:
            query = query.filter(EmailTemplate.category == category)
        
        if target_role:
            query = query.filter(EmailTemplate.target_role == target_role)
        
        if is_active is not None:
            query = query.filter(EmailTemplate.is_active == is_active)
        
        total = query.count()
        templates = query.order_by(EmailTemplate.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
        
        return {
            "templates": [{
                "id": t.id,
                "name": t.name,
                "subject": t.subject,
                "body": t.body,
                "target_role": t.target_role,
                "category": t.category,
                "is_active": t.is_active,
                "created_by": t.created_by,
                "created_at": t.created_at,
                "updated_at": t.updated_at
            } for t in templates],
            "total": total,
            "page": page,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Get email templates error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch email templates")

@router.get("/{template_id}")
async def get_email_template(
    template_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get a specific email template by ID"""
    try:
        template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Email template not found")
        
        return {
            "id": template.id,
            "name": template.name,
            "subject": template.subject,
            "body": template.body,
            "target_role": template.target_role,
            "category": template.category,
            "is_active": template.is_active,
            "created_by": template.created_by,
            "created_at": template.created_at,
            "updated_at": template.updated_at
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get email template error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch email template")

@router.post("/")
async def create_email_template(
    template_data: EmailTemplateCreate,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Create a new email template"""
    try:
        # Check if template name already exists
        existing_template = db.query(EmailTemplate).filter(EmailTemplate.name == template_data.name).first()
        if existing_template:
            raise HTTPException(status_code=400, detail="Template name already exists")
        
        template = EmailTemplate(
            name=template_data.name,
            subject=template_data.subject,
            body=template_data.body,
            target_role=template_data.target_role,
            category=template_data.category,
            is_active=template_data.is_active,
            created_by=current_admin.id
        )
        
        db.add(template)
        db.commit()
        db.refresh(template)
        
        return {
            "message": "Email template created successfully",
            "template_id": template.id,
            "template": {
                "id": template.id,
                "name": template.name,
                "subject": template.subject,
                "body": template.body,
                "target_role": template.target_role,
                "category": template.category,
                "is_active": template.is_active,
                "created_at": template.created_at
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create email template error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create email template")

@router.put("/{template_id}")
async def update_email_template(
    template_id: int,
    template_data: EmailTemplateUpdate,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Update an existing email template"""
    try:
        template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Email template not found")
        
        # Check if new name already exists (if name is being updated)
        if template_data.name and template_data.name != template.name:
            existing_template = db.query(EmailTemplate).filter(
                EmailTemplate.name == template_data.name,
                EmailTemplate.id != template_id
            ).first()
            if existing_template:
                raise HTTPException(status_code=400, detail="Template name already exists")
        
        # Update fields
        update_data = template_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(template, field, value)
        
        db.commit()
        db.refresh(template)
        
        return {
            "message": "Email template updated successfully",
            "template": {
                "id": template.id,
                "name": template.name,
                "subject": template.subject,
                "body": template.body,
                "target_role": template.target_role,
                "category": template.category,
                "is_active": template.is_active,
                "updated_at": template.updated_at
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update email template error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update email template")

@router.delete("/{template_id}")
async def delete_email_template(
    template_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Delete an email template"""
    try:
        template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Email template not found")
        
        template_name = template.name
        
        # Remove template reference from any campaigns using it
        campaigns_updated = db.query(EmailCampaign).filter(EmailCampaign.template_id == template_id).update({"template_id": None})
        
        if campaigns_updated > 0:
            logger.info(f"Updated {campaigns_updated} campaigns to remove template reference")
        
        db.delete(template)
        db.commit()
        
        return {"message": f"Email template '{template_name}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete email template error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete email template")

@router.get("/categories/list")
async def get_template_categories(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get list of all template categories"""
    try:
        categories = db.query(EmailTemplate.category).distinct().all()
        return {
            "categories": [cat[0] for cat in categories if cat[0]]
        }
    except Exception as e:
        logger.error(f"Get template categories error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch template categories")

@router.get("/roles/list")
async def get_target_roles(
    current_admin = Depends(get_current_admin_or_presenter)
):
    """Get list of available target roles"""
    return {
        "roles": ["All", "Student", "Admin", "Presenter", "Mentor"]
    }