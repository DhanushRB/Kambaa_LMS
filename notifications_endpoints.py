from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from auth import get_current_user, verify_token
from database import Notification, NotificationPreference, get_db, User, Admin, Presenter, Mentor
from notification_service import NotificationService, render_template
from schemas import (
    NotificationResponse,
    MarkReadRequest,
    PreferenceUpdate,
    NotificationCreate,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])

def get_current_any_user(token_data: dict = Depends(verify_token), db: Session = Depends(get_db)):
    """Get current user from any user table, create User record for admins if needed"""
    username = token_data.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token: no username")
    
    # Try User table first (students)
    user = db.query(User).filter(User.username == username).first()
    if user:
        return user
    
    # Check if it's an admin
    admin = db.query(Admin).filter(Admin.username == username).first()
    if admin:
        # Create a corresponding User record for notifications
        user = User(
            username=admin.username,
            email=admin.email,
            password_hash=admin.password_hash,
            role="Admin",
            college="Admin",
            department="Administration",
            year="N/A",
            user_type="Admin"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    # Check other user types and create User records as needed
    presenter = db.query(Presenter).filter(Presenter.username == username).first()
    if presenter:
        user = User(
            username=presenter.username,
            email=presenter.email,
            password_hash=presenter.password_hash,
            role="Presenter",
            college="Staff",
            department="Presentation",
            year="N/A",
            user_type="Presenter"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    mentor = db.query(Mentor).filter(Mentor.username == username).first()
    if mentor:
        user = User(
            username=mentor.username,
            email=mentor.email,
            password_hash=mentor.password_hash,
            role="Mentor",
            college="Staff",
            department="Mentoring",
            year="N/A",
            user_type="Mentor"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    raise HTTPException(status_code=404, detail="User not found in any table")


@router.get("", response_model=List[NotificationResponse])
def list_notifications(
    skip: int = 0,
    limit: int = 50,
    is_read: Optional[bool] = None,
    current_user=Depends(get_current_any_user),
    db: Session = Depends(get_db),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)
    notifications = (
        query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()
    )
    return notifications


@router.get("/unread-count")
def unread_count(current_user=Depends(get_current_any_user), db: Session = Depends(get_db)):
    count = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .count()
    )
    return {"unread_count": count}


@router.post("/mark-read")
def mark_read(
    payload: MarkReadRequest,
    current_user=Depends(get_current_any_user),
    db: Session = Depends(get_db),
):
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == payload.notification_id,
            Notification.user_id == current_user.id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    db.commit()
    return {"message": "Notification marked as read"}


@router.post("/mark-all-read")
def mark_all_read(
    current_user=Depends(get_current_any_user), db: Session = Depends(get_db)
):
    (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .update({Notification.is_read: True})
    )
    db.commit()
    return {"message": "All notifications marked as read"}


@router.get("/preferences")
def get_preferences(
    current_user=Depends(get_current_any_user), db: Session = Depends(get_db)
):
    service = NotificationService(db)
    prefs = service._get_preferences(current_user.id)
    return {
        "email_enabled": prefs.email_enabled,
        "in_app_enabled": prefs.in_app_enabled,
    }


@router.post("/preferences")
def update_preferences(
    payload: PreferenceUpdate,
    current_user=Depends(get_current_any_user),
    db: Session = Depends(get_db),
):
    service = NotificationService(db)
    prefs = service.update_preferences(
        current_user.id,
        email_enabled=payload.email_enabled,
        in_app_enabled=payload.in_app_enabled,
    )
    return {
        "email_enabled": prefs.email_enabled,
        "in_app_enabled": prefs.in_app_enabled,
    }


@router.post("/send-test")
def send_test_notification(
    payload: NotificationCreate,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_any_user),
    db: Session = Depends(get_db),
):
    """
    Helper endpoint to validate email + in-app wiring.
    Only allows sending to the authenticated user_id in payload for safety.
    """
    if payload.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Can only send to self in test mode")

    service = NotificationService(db)
    created = service.send_in_app_notification(
        user_id=payload.user_id,
        title=payload.title,
        message=payload.message,
        notification_type=payload.type,
        action_url=payload.action_url,
    )

    # Email mirror (optional)
    if current_user.email:
        email_body = render_template(
            "<p>{message}</p>",
            {"message": payload.message, "username": current_user.username},
        )
        service.send_email_notification(
            user_id=current_user.id,
            email=current_user.email,
            subject=payload.title,
            body=email_body,
            background_tasks=background_tasks,
        )

    return {
        "notification_id": created.id if created else None,
        "email": current_user.email,
    }
