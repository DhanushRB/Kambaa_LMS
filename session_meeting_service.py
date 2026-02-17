from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import SessionMeeting, CalendarEvent
from calendar_blocking_service import CalendarBlockingService
import logging

logger = logging.getLogger(__name__)

def create_session_meeting(db: Session, session_id: int, title: str, meeting_url: str,
                          description: str = None, scheduled_time: datetime = None, 
                          duration_minutes: int = 60, created_by: int = None, user_type: str = "Admin"):
    """Create session meeting with automatic calendar blocking"""
    
    try:
        # Check for time conflicts if scheduled
        if scheduled_time:
            end_time = scheduled_time + timedelta(minutes=duration_minutes)
            if CalendarBlockingService.check_time_conflict(db, scheduled_time, end_time):
                raise ValueError(f"Time slot conflict: {scheduled_time} - {end_time} is already blocked")
        
        # Create session meeting
        meeting = SessionMeeting(
            session_id=session_id,
            title=title,
            description=description,
            meeting_datetime=scheduled_time,
            duration_minutes=duration_minutes,
            meeting_url=meeting_url,
            location=meeting_url,
            created_by=created_by
        )
        
        db.add(meeting)
        db.flush()
        
        # Auto-create calendar block if scheduled
        if scheduled_time:
            CalendarBlockingService.create_meeting_block(db, meeting, created_by, user_type)
            logger.info(f"Auto-created calendar block for meeting: {title}")
        
        db.commit()
        return meeting
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create session meeting: {str(e)}")
        raise

def update_session_meeting(db: Session, meeting_id: int, title: str = None, meeting_url: str = None,
                          description: str = None, scheduled_time: datetime = None, 
                          duration_minutes: int = None):
    """Update session meeting with calendar block update"""
    
    try:
        meeting = db.query(SessionMeeting).filter(SessionMeeting.id == meeting_id).first()
        if not meeting:
            raise ValueError("Meeting not found")
        
        original_time = meeting.meeting_datetime
        
        # Check for conflicts if rescheduling
        if scheduled_time and scheduled_time != original_time:
            end_time = scheduled_time + timedelta(minutes=duration_minutes or meeting.duration_minutes)
            if CalendarBlockingService.check_time_conflict(db, scheduled_time, end_time):
                raise ValueError(f"Time slot conflict: {scheduled_time} - {end_time} is already blocked")
        
        # Update meeting
        if title is not None:
            meeting.title = title
        if meeting_url is not None:
            meeting.meeting_url = meeting_url
            meeting.location = meeting_url
        if description is not None:
            meeting.description = description
        if scheduled_time is not None:
            meeting.meeting_datetime = scheduled_time
        if duration_minutes is not None:
            meeting.duration_minutes = duration_minutes
        
        meeting.updated_at = datetime.utcnow()
        
        # Update calendar block if time changed
        if scheduled_time and original_time and scheduled_time != original_time:
            CalendarBlockingService.update_meeting_block(db, meeting, original_time)
            logger.info(f"Updated calendar block for meeting: {meeting.title}")
        
        db.commit()
        return meeting
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update session meeting: {str(e)}")
        raise

def delete_session_meeting(db: Session, meeting_id: int):
    """Delete session meeting and its calendar block"""
    
    try:
        meeting = db.query(SessionMeeting).filter(SessionMeeting.id == meeting_id).first()
        if not meeting:
            raise ValueError("Meeting not found")
        
        # Delete calendar block
        CalendarBlockingService.delete_meeting_block(db, meeting_id)
        
        # Delete meeting
        db.delete(meeting)
        db.commit()
        
        logger.info(f"Deleted meeting and calendar block: {meeting.title}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete session meeting: {str(e)}")
        raise

def get_session_meetings(db: Session, session_id: int):
    """Get all meetings for a session"""
    try:
        return db.query(SessionMeeting).filter(SessionMeeting.session_id == session_id).all()
    except Exception as e:
        logger.error(f"Failed to get session meetings: {str(e)}")
        raise