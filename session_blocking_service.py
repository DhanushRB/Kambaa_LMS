from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import Session as SessionModel, CalendarEvent
from calendar_blocking_service import CalendarBlockingService
import logging

logger = logging.getLogger(__name__)

def create_session_with_blocking(db: Session, module_id: int, session_number: int, title: str,
                               description: str = None, scheduled_time: datetime = None,
                               duration_minutes: int = 120, zoom_link: str = None,
                               syllabus_content: str = None, created_by: int = None, user_type: str = "Admin"):
    """Create session with automatic calendar blocking"""
    
    try:
        # Check for time conflicts if scheduled
        if scheduled_time:
            end_time = scheduled_time + timedelta(minutes=duration_minutes)
            if CalendarBlockingService.check_time_conflict(db, scheduled_time, end_time):
                raise ValueError(f"Time slot conflict: {scheduled_time} - {end_time} is already blocked")
        
        # Create session
        session = SessionModel(
            module_id=module_id,
            session_number=session_number,
            title=title,
            description=description,
            scheduled_time=scheduled_time,
            duration_minutes=duration_minutes,
            zoom_link=zoom_link,
            syllabus_content=syllabus_content
        )
        
        db.add(session)
        db.flush()
        
        # Auto-create calendar block if scheduled
        if scheduled_time:
            CalendarBlockingService.create_session_block(db, session, created_by, user_type)
            logger.info(f"Auto-created calendar block for session: {title}")
        
        db.commit()
        return session
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create session: {str(e)}")
        raise

def update_session_with_blocking(db: Session, session_id: int, title: str = None,
                               description: str = None, scheduled_time: datetime = None,
                               duration_minutes: int = None, zoom_link: str = None,
                               syllabus_content: str = None):
    """Update session with calendar block update"""
    
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise ValueError("Session not found")
        
        original_time = session.scheduled_time
        
        # Check for conflicts if rescheduling
        if scheduled_time and scheduled_time != original_time:
            end_time = scheduled_time + timedelta(minutes=duration_minutes or session.duration_minutes)
            if CalendarBlockingService.check_time_conflict(db, scheduled_time, end_time):
                raise ValueError(f"Time slot conflict: {scheduled_time} - {end_time} is already blocked")
        
        # Update session
        if title is not None:
            session.title = title
        if description is not None:
            session.description = description
        if scheduled_time is not None:
            session.scheduled_time = scheduled_time
        if duration_minutes is not None:
            session.duration_minutes = duration_minutes
        if zoom_link is not None:
            session.zoom_link = zoom_link
        if syllabus_content is not None:
            session.syllabus_content = syllabus_content
        
        # Update calendar block if time changed
        if scheduled_time and original_time and scheduled_time != original_time:
            CalendarBlockingService.update_session_block(db, session, original_time)
            logger.info(f"Updated calendar block for session: {session.title}")
        elif scheduled_time and not original_time:
            # Session was unscheduled, now being scheduled
            CalendarBlockingService.create_session_block(db, session, None, "Admin")
            logger.info(f"Created new calendar block for session: {session.title}")
        elif not scheduled_time and original_time:
            # Session was scheduled, now being unscheduled
            CalendarBlockingService.delete_session_block(db, session_id)
            logger.info(f"Removed calendar block for session: {session.title}")
        
        db.commit()
        return session
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update session: {str(e)}")
        raise

def delete_session_with_blocking(db: Session, session_id: int):
    """Delete session and its calendar block"""
    
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise ValueError("Session not found")
        
        # Delete calendar block
        CalendarBlockingService.delete_session_block(db, session_id)
        
        # Delete session
        db.delete(session)
        db.commit()
        
        logger.info(f"Deleted session and calendar block: {session.title}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete session: {str(e)}")
        raise

def get_session_conflicts(db: Session, session_id: int):
    """Get potential conflicts for a session"""
    
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session or not session.scheduled_time:
            return []
        
        end_time = session.scheduled_time + timedelta(minutes=session.duration_minutes or 120)
        
        # Get blocked slots in the same time range
        blocked_slots = CalendarBlockingService.get_blocked_slots(
            db, session.scheduled_time, end_time
        )
        
        # Filter out the session's own block
        conflicts = [
            slot for slot in blocked_slots 
            if slot["id"] != f"session_{session_id}"
        ]
        
        return conflicts
    except Exception as e:
        logger.error(f"Failed to get session conflicts: {str(e)}")
        raise