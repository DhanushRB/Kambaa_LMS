from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from database import get_db, User, Course, Assignment
from auth import get_current_admin, get_current_user
from enhanced_email_service import EmailService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email", tags=["email"])

# Pydantic models
class EmailTestRequest(BaseModel):
    to_email: EmailStr
    subject: str
    message: str

class BulkEmailRequest(BaseModel):
    user_ids: List[int]
    subject: str
    message: str

class CourseEnrollmentEmailRequest(BaseModel):
    user_id: int
    course_id: int

class AssignmentNotificationRequest(BaseModel):
    user_ids: List[int]
    assignment_id: int

class SessionReminderRequest(BaseModel):
    user_ids: List[int]
    session_id: int

@router.get("/test-connection")
async def test_smtp_connection(
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Test SMTP connection"""
    try:
        email_service = EmailService(db)
        success, message = email_service.test_smtp_connection()
        
        return {
            "success": success,
            "message": message,
            "smtp_configured": all([
                email_service.EMAIL_HOST,
                email_service.EMAIL_USERNAME,
                email_service.EMAIL_PASSWORD
            ])
        }
    except Exception as e:
        logger.error(f"SMTP test error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"SMTP test failed: {str(e)}")

@router.post("/send-test")
async def send_test_email(
    request: EmailTestRequest,
    background_tasks: BackgroundTasks,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Send a test email"""
    try:
        email_service = EmailService(db)
        
        # Create a simple HTML message
        html_content = f"""
        <html>
        <body>
            <h2>Test Email from Kambaa AI LMS</h2>
            <p>{request.message}</p>
            <p>This is a test email sent by {current_admin.username}</p>
            <hr>
            <small>Sent from Kambaa AI Learning Management System</small>
        </body>
        </html>
        """
        
        result = email_service._send_email(
            user_id=current_admin.id,
            to_email=request.to_email,
            subject=request.subject,
            html_content=html_content,
            background_tasks=background_tasks
        )
        
        return {
            "message": "Test email queued successfully",
            "email_log_id": result.id if result else None,
            "recipient": request.to_email
        }
    except Exception as e:
        logger.error(f"Send test email error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send test email: {str(e)}")

@router.post("/send-welcome")
async def send_welcome_email(
    user_id: int,
    background_tasks: BackgroundTasks,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Send welcome email to a user"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        email_service = EmailService(db)
        result = email_service.send_welcome_email(user_id, background_tasks)
        
        return {
            "message": f"Welcome email sent to {user.email}",
            "email_log_id": result.id if result else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send welcome email error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send welcome email: {str(e)}")

@router.post("/send-enrollment-confirmation")
async def send_enrollment_confirmation(
    request: CourseEnrollmentEmailRequest,
    background_tasks: BackgroundTasks,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Send course enrollment confirmation email"""
    try:
        user = db.query(User).filter(User.id == request.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        course = db.query(Course).filter(Course.id == request.course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        email_service = EmailService(db)
        result = email_service.send_course_enrollment_email(
            user_id=request.user_id,
            course_title=course.title,
            course_description=course.description or "No description available",
            background_tasks=background_tasks
        )
        
        return {
            "message": f"Enrollment confirmation sent to {user.email}",
            "email_log_id": result.id if result else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send enrollment confirmation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send enrollment confirmation: {str(e)}")

@router.post("/send-assignment-notification")
async def send_assignment_notification(
    request: AssignmentNotificationRequest,
    background_tasks: BackgroundTasks,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Send assignment notification to multiple users"""
    try:
        assignment = db.query(Assignment).filter(Assignment.id == request.assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        email_service = EmailService(db)
        results = []
        
        for user_id in request.user_ids:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                result = email_service.send_assignment_notification(
                    user_id=user_id,
                    assignment_title=assignment.title,
                    assignment_description=assignment.description,
                    due_date=str(assignment.due_date),
                    background_tasks=background_tasks
                )
                results.append({
                    "user_id": user_id,
                    "email": user.email,
                    "status": "queued",
                    "email_log_id": result.id if result else None
                })
        
        return {
            "message": f"Assignment notifications sent to {len(results)} users",
            "results": results
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send assignment notification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send assignment notifications: {str(e)}")

@router.post("/send-bulk-notification")
async def send_bulk_notification(
    request: BulkEmailRequest,
    background_tasks: BackgroundTasks,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Send bulk notification to multiple users"""
    try:
        email_service = EmailService(db)
        results = email_service.send_bulk_notification(
            user_ids=request.user_ids,
            subject=request.subject,
            message=request.message,
            background_tasks=background_tasks
        )
        
        return {
            "message": f"Bulk notification sent to {len(request.user_ids)} users",
            "queued_emails": len(results)
        }
    except Exception as e:
        logger.error(f"Send bulk notification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send bulk notification: {str(e)}")

@router.get("/logs")
async def get_email_logs(
    page: int = 1,
    limit: int = 50,
    status: Optional[str] = None,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get email logs with pagination"""
    try:
        from database import EmailLog
        
        query = db.query(EmailLog)
        
        if status:
            query = query.filter(EmailLog.status == status)
        
        total = query.count()
        logs = query.order_by(EmailLog.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
        
        return {
            "logs": [{
                "id": log.id,
                "user_id": log.user_id,
                "email": log.email,
                "subject": log.subject,
                "status": log.status,
                "error_message": log.error_message,
                "created_at": log.created_at
            } for log in logs],
            "total": total,
            "page": page,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Get email logs error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch email logs: {str(e)}")

@router.get("/stats")
async def get_email_stats(
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get email statistics"""
    try:
        from database import EmailLog
        from sqlalchemy import func
        
        total_emails = db.query(EmailLog).count()
        sent_emails = db.query(EmailLog).filter(EmailLog.status == "sent").count()
        failed_emails = db.query(EmailLog).filter(EmailLog.status == "failed").count()
        queued_emails = db.query(EmailLog).filter(EmailLog.status == "queued").count()
        
        # Get recent activity (last 7 days)
        from datetime import datetime, timedelta
        week_ago = datetime.now() - timedelta(days=7)
        recent_emails = db.query(EmailLog).filter(EmailLog.created_at >= week_ago).count()
        
        return {
            "total_emails": total_emails,
            "sent_emails": sent_emails,
            "failed_emails": failed_emails,
            "queued_emails": queued_emails,
            "success_rate": (sent_emails / total_emails * 100) if total_emails > 0 else 0,
            "recent_activity": recent_emails
        }
    except Exception as e:
        logger.error(f"Get email stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch email stats: {str(e)}")

# User preference endpoints
@router.get("/preferences")
async def get_email_preferences(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user email preferences"""
    try:
        from database import NotificationPreference
        
        prefs = db.query(NotificationPreference).filter(
            NotificationPreference.user_id == current_user.id
        ).first()
        
        if not prefs:
            prefs = NotificationPreference(user_id=current_user.id)
            db.add(prefs)
            db.commit()
            db.refresh(prefs)
        
        return {
            "email_enabled": prefs.email_enabled,
            "in_app_enabled": prefs.in_app_enabled
        }
    except Exception as e:
        logger.error(f"Get email preferences error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch preferences: {str(e)}")

@router.post("/preferences")
async def update_email_preferences(
    email_enabled: bool,
    in_app_enabled: bool,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user email preferences"""
    try:
        from database import NotificationPreference
        
        prefs = db.query(NotificationPreference).filter(
            NotificationPreference.user_id == current_user.id
        ).first()
        
        if not prefs:
            prefs = NotificationPreference(user_id=current_user.id)
            db.add(prefs)
        
        prefs.email_enabled = email_enabled
        prefs.in_app_enabled = in_app_enabled
        
        db.commit()
        
        return {
            "message": "Preferences updated successfully",
            "email_enabled": prefs.email_enabled,
            "in_app_enabled": prefs.in_app_enabled
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Update email preferences error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update preferences: {str(e)}")