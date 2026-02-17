from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from database import (
    get_db, User, Admin, Presenter, Mentor, 
    EmailTemplate, EmailCampaign, EmailRecipient, EmailLog
)
from auth import get_current_admin_or_presenter
from notification_service import NotificationService
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

class CampaignTemplate(BaseModel):
    name: str
    subject: str
    body: str
    target_role: str
    category: Optional[str] = "general"
    is_active: Optional[bool] = True

class CampaignCreate(BaseModel):
    name: str
    template_id: int
    target_role: str
    scheduled_time: Optional[datetime] = None

class CampaignSend(BaseModel):
    template_id: int
    target_role: str
    schedule_time: Optional[datetime] = None
    test_email: Optional[EmailStr] = None

@router.post("/templates")
async def create_template(
    template: CampaignTemplate,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Create professional email campaign template"""
    try:
        db_template = EmailTemplate(
            name=template.name,
            subject=template.subject,
            body=template.body,
            target_role=template.target_role,
            category=template.category,
            is_active=template.is_active,
            created_by=current_admin.id
        )
        db.add(db_template)
        db.commit()
        db.refresh(db_template)
        
        return {
            "message": "Template created successfully",
            "template_id": db_template.id,
            "name": db_template.name,
            "category": db_template.category
        }
    except Exception as e:
        logger.error(f"Create template error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create template")

@router.get("/templates")
async def get_templates(
    category: Optional[str] = None,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get all campaign templates"""
    try:
        query = db.query(EmailTemplate).filter(EmailTemplate.is_active == True)
        if category:
            query = query.filter(EmailTemplate.category == category)
        
        templates = query.all()
        
        return {
            "templates": [
                {
                    "id": t.id,
                    "name": t.name,
                    "subject": t.subject,
                    "body": t.body,
                    "target_role": t.target_role,
                    "category": t.category,
                    "created_at": t.created_at.isoformat()
                }
                for t in templates
            ]
        }
    except Exception as e:
        logger.error(f"Get templates error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get templates")

@router.post("/create")
async def create_campaign(
    campaign: CampaignCreate,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Create new email campaign"""
    try:
        # Verify template exists
        template = db.query(EmailTemplate).filter(EmailTemplate.id == campaign.template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Determine initial status
        initial_status = "scheduled" if campaign.scheduled_time else "draft"
        
        # Create campaign
        db_campaign = EmailCampaign(
            name=campaign.name,
            template_id=campaign.template_id,
            target_role=campaign.target_role,
            scheduled_time=campaign.scheduled_time,
            created_by=current_admin.id,
            status=initial_status
        )
        db.add(db_campaign)
        db.commit()
        db.refresh(db_campaign)
        
        if campaign.scheduled_time:
            logger.info(f"Campaign {db_campaign.id} scheduled for {campaign.scheduled_time}")
        else:
            logger.info(f"Campaign {db_campaign.id} created as draft")
        
        return {
            "message": "Campaign created successfully",
            "campaign_id": db_campaign.id,
            "name": db_campaign.name,
            "status": db_campaign.status
        }
    except Exception as e:
        logger.error(f"Create campaign error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create campaign")

async def send_campaign_immediately(campaign_id: int, db: Session):
    """Send campaign immediately without background tasks"""
    from notification_service import NotificationService
    from database import EmailTemplate, EmailRecipient, User, Admin, Presenter, Mentor, UserCohort, Cohort
    
    try:
        # Get campaign
        campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
        if not campaign:
            logger.error(f"Campaign {campaign_id} not found")
            return
        
        # Get template
        template = db.query(EmailTemplate).filter(EmailTemplate.id == campaign.template_id).first()
        if not template:
            logger.error(f"Template {campaign.template_id} not found for campaign {campaign_id}")
            return
        
        # Get target users based on target_role
        target_users = []
        
        # Check if target_role is a cohort (starts with "cohort_")
        if campaign.target_role.startswith("cohort_"):
            try:
                cohort_id = int(campaign.target_role.replace("cohort_", ""))
                # Get users in this specific cohort
                user_cohorts = db.query(UserCohort).filter(UserCohort.cohort_id == cohort_id).all()
                for uc in user_cohorts:
                    user = db.query(User).filter(User.id == uc.user_id).first()
                    if user:
                        target_users.append(user)
                logger.info(f"Found {len(target_users)} users in cohort {cohort_id}")
            except ValueError:
                logger.error(f"Invalid cohort ID in target_role: {campaign.target_role}")
                return
        else:
            # Regular role-based targeting
            if campaign.target_role == "Student":
                target_users = db.query(User).filter(User.role == "Student").all()
            elif campaign.target_role == "Admin":
                target_users = db.query(Admin).all()
            elif campaign.target_role == "Presenter":
                target_users = db.query(Presenter).all()
            elif campaign.target_role == "Mentor":
                target_users = db.query(Mentor).all()
            elif campaign.target_role == "All":
                users = db.query(User).all()
                admins = db.query(Admin).all()
                presenters = db.query(Presenter).all()
                mentors = db.query(Mentor).all()
                target_users = users + admins + presenters + mentors
        
        if not target_users:
            logger.warning(f"No target users found for campaign {campaign_id} with target_role {campaign.target_role}")
            campaign.status = "completed"
            campaign.sent_count = 0
            campaign.completed_at = datetime.utcnow()
            db.commit()
            return
        
        # Update campaign status to sending
        campaign.status = "sending"
        campaign.started_at = datetime.utcnow()
        db.commit()
        
        # Create recipients and send emails
        service = NotificationService(db)
        sent_count = 0
        
        for user in target_users:
            if user.email:
                try:
                    # Create recipient record
                    recipient = EmailRecipient(
                        campaign_id=campaign.id,
                        user_id=getattr(user, 'id', None),
                        email=user.email,
                        status="pending"
                    )
                    db.add(recipient)
                    
                    # Send email
                    email_body = template.body.replace("{username}", getattr(user, 'username', user.email))
                    email_body = email_body.replace("{email}", user.email)
                    
                    # Send email synchronously
                    email_log = service.send_email_notification(
                        user_id=getattr(user, 'id', None),
                        email=user.email,
                        subject=template.subject,
                        body=email_body
                    )
                    
                    if email_log.status in ["sent", "queued"]:
                        recipient.status = "sent"
                        recipient.sent_at = datetime.utcnow()
                        sent_count += 1
                    else:
                        recipient.status = "failed"
                        recipient.error_message = email_log.error_message
                        
                except Exception as e:
                    logger.error(f"Failed to send email to {user.email}: {str(e)}")
                    if 'recipient' in locals():
                        recipient.status = "failed"
                        recipient.error_message = str(e)
        
        # Update campaign with final counts and mark as completed
        campaign.sent_count = sent_count
        campaign.status = "completed"
        campaign.completed_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"Campaign {campaign_id} sent immediately to {sent_count} recipients")
        
    except Exception as e:
        logger.error(f"Error sending campaign {campaign_id} immediately: {str(e)}")
        # Mark campaign as failed
        try:
            campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
            if campaign:
                campaign.status = "failed"
                db.commit()
        except:
            pass

@router.post("/send/{campaign_id}")
async def send_campaign(
    campaign_id: int,
    background_tasks: BackgroundTasks,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Send email campaign"""
    try:
        # Use the immediate send function
        await send_campaign_immediately(campaign_id, db)
        
        # Get updated campaign status
        campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        return {
            "message": f"Campaign sent to {campaign.sent_count or 0} recipients",
            "campaign_id": campaign.id,
            "sent_count": campaign.sent_count or 0,
            "status": campaign.status
        }
    except Exception as e:
        logger.error(f"Send campaign error: {str(e)}")
        # Mark campaign as failed if error occurs
        try:
            campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
            if campaign:
                campaign.status = "failed"
                db.commit()
        except:
            pass
        raise HTTPException(status_code=500, detail="Failed to send campaign")

@router.get("/list")
async def list_campaigns(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get all campaigns"""
    try:
        campaigns = db.query(EmailCampaign).order_by(EmailCampaign.created_at.desc()).all()
        
        return {
            "campaigns": [
                {
                    "id": c.id,
                    "name": c.name,
                    "target_role": c.target_role,
                    "status": c.status,
                    "sent_count": c.sent_count,
                    "delivered_count": c.delivered_count,
                    "failed_count": c.failed_count,
                    "scheduled_time": c.scheduled_time.isoformat() if c.scheduled_time else None,
                    "created_at": c.created_at.isoformat(),
                    "template_name": c.template.name if c.template else "Unknown"
                }
                for c in campaigns
            ]
        }
    except Exception as e:
        logger.error(f"List campaigns error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list campaigns")

@router.post("/test")
async def send_test_email(
    request_data: dict,
    background_tasks: BackgroundTasks,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Send test email to verify template"""
    try:
        template_id = request_data.get('template_id')
        test_email = request_data.get('test_email')
        
        if not template_id or not test_email:
            raise HTTPException(status_code=400, detail="Template ID and test email are required")
        
        template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        service = NotificationService(db)
        
        # Replace placeholders with test data
        email_body = template.body.replace("{username}", "Test User")
        email_body = email_body.replace("{email}", test_email)
        
        service.send_email_notification(
            user_id=None,
            email=test_email,
            subject=f"[TEST] {template.subject}",
            body=email_body,
            background_tasks=background_tasks
        )
        
        return {
            "message": f"Test email sent to {test_email}",
            "template_id": template_id,
            "status": "sent"
        }
    except Exception as e:
        logger.error(f"Send test email error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send test email")

@router.put("/templates/{template_id}")
async def update_template(
    template_id: int,
    template: CampaignTemplate,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Update email template"""
    try:
        db_template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if not db_template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        db_template.name = template.name
        db_template.subject = template.subject
        db_template.body = template.body
        db_template.target_role = template.target_role
        db_template.category = template.category
        db_template.is_active = template.is_active
        db_template.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(db_template)
        
        return {
            "message": "Template updated successfully",
            "template_id": db_template.id,
            "name": db_template.name
        }
    except Exception as e:
        logger.error(f"Update template error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update template")

@router.put("/{campaign_id}")
async def update_campaign(
    campaign_id: int,
    campaign: CampaignCreate,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Update email campaign"""
    try:
        db_campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
        if not db_campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Only allow updates if campaign is in draft status
        if db_campaign.status != "draft":
            raise HTTPException(status_code=400, detail="Can only update draft campaigns")
        
        # Verify template exists
        template = db.query(EmailTemplate).filter(EmailTemplate.id == campaign.template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        db_campaign.name = campaign.name
        db_campaign.template_id = campaign.template_id
        db_campaign.target_role = campaign.target_role
        db_campaign.scheduled_time = campaign.scheduled_time
        
        db.commit()
        db.refresh(db_campaign)
        
        return {
            "message": "Campaign updated successfully",
            "campaign_id": db_campaign.id,
            "name": db_campaign.name,
            "status": db_campaign.status
        }
    except Exception as e:
        logger.error(f"Update campaign error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update campaign")
@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Delete email template"""
    try:
        template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        db.delete(template)
        db.commit()
        
        return {"message": "Template deleted successfully"}
    except Exception as e:
        logger.error(f"Delete template error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete template")

@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Delete email campaign"""
    try:
        campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Delete related recipients first
        db.query(EmailRecipient).filter(EmailRecipient.campaign_id == campaign_id).delete()
        
        db.delete(campaign)
        db.commit()
        
        return {"message": "Campaign deleted successfully"}
    except Exception as e:
        logger.error(f"Delete campaign error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete campaign")

@router.get("/stats")
async def get_campaign_stats(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get comprehensive campaign statistics"""
    try:
        student_count = db.query(User).filter(User.role == "Student").count()
        admin_count = db.query(Admin).count()
        presenter_count = db.query(Presenter).count()
        mentor_count = db.query(Mentor).count()
        total_users = student_count + admin_count + presenter_count + mentor_count
        
        total_campaigns = db.query(EmailCampaign).count()
        active_campaigns = db.query(EmailCampaign).filter(EmailCampaign.status.in_(["sending", "scheduled"])).count()
        
        total_sent = db.query(EmailRecipient).filter(EmailRecipient.status == "sent").count()
        total_delivered = db.query(EmailRecipient).filter(EmailRecipient.status == "delivered").count()
        
        delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
        
        return {
            "audience_stats": {
                "total_users": total_users,
                "students": student_count,
                "admins": admin_count,
                "presenters": presenter_count,
                "mentors": mentor_count
            },
            "campaign_performance": {
                "total_campaigns": total_campaigns,
                "active_campaigns": active_campaigns,
                "total_sent": total_sent,
                "total_delivered": total_delivered,
                "delivery_rate": round(delivery_rate, 2)
            }
        }
    except Exception as e:
        logger.error(f"Get stats error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

@router.post("/scheduler/trigger")
async def trigger_scheduler(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Manually trigger scheduler check for testing"""
    try:
        from campaign_scheduler import trigger_scheduler_check
        await trigger_scheduler_check()
        
        # Also check current scheduled campaigns
        from datetime import datetime
        now = datetime.utcnow()
        scheduled_campaigns = db.query(EmailCampaign).filter(
            EmailCampaign.status == "scheduled",
            EmailCampaign.scheduled_time.isnot(None)
        ).all()
        
        campaign_info = []
        for campaign in scheduled_campaigns:
            time_diff = campaign.scheduled_time - now
            campaign_info.append({
                "id": campaign.id,
                "name": campaign.name,
                "scheduled_time": campaign.scheduled_time.isoformat(),
                "time_remaining": str(time_diff),
                "ready_to_send": campaign.scheduled_time <= now
            })
        
        return {
            "message": "Scheduler check triggered successfully",
            "current_time": now.isoformat(),
            "scheduled_campaigns": campaign_info
        }
    except Exception as e:
        logger.error(f"Trigger scheduler error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to trigger scheduler")