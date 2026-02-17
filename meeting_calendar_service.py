from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from database import CalendarEvent, SessionContent

def create_meeting_calendar_event(
    db: Session,
    meeting_title: str,
    meeting_description: str,
    meeting_url: str,
    scheduled_time: datetime,
    created_by_id: int
):
    """
    Automatically create a calendar event when a meeting is scheduled
    """
    try:
        # Create calendar event for the meeting
        calendar_event = CalendarEvent(
            title=f"Meeting: {meeting_title}",
            description=meeting_description or f"Scheduled meeting: {meeting_title}",
            start_datetime=scheduled_time,
            end_datetime=scheduled_time + timedelta(hours=1),  # Default 1 hour duration
            event_type="meeting",
            location=meeting_url,
            created_by_admin_id=created_by_id
        )
        
        db.add(calendar_event)
        db.commit()
        db.refresh(calendar_event)
        
        return calendar_event.id
    except Exception as e:
        db.rollback()
        raise e

def update_meeting_calendar_event(
    db: Session,
    meeting_title: str,
    meeting_description: str,
    meeting_url: str,
    scheduled_time: datetime,
    original_title: str
):
    """
    Update existing calendar event when meeting is modified
    """
    try:
        # Find existing calendar event by title pattern
        existing_event = db.query(CalendarEvent).filter(
            CalendarEvent.title == f"Meeting: {original_title}",
            CalendarEvent.event_type == "meeting"
        ).first()
        
        if existing_event:
            existing_event.title = f"Meeting: {meeting_title}"
            existing_event.description = meeting_description
            existing_event.start_datetime = scheduled_time
            existing_event.end_datetime = scheduled_time + timedelta(hours=1)
            existing_event.location = meeting_url
            existing_event.updated_at = datetime.utcnow()
            
            db.commit()
            return existing_event.id
        
        return None
    except Exception as e:
        db.rollback()
        raise e

def delete_meeting_calendar_event(
    db: Session,
    meeting_title: str
):
    """
    Delete calendar event when meeting is removed
    """
    try:
        # Find and delete the calendar event
        event_to_delete = db.query(CalendarEvent).filter(
            CalendarEvent.title == f"Meeting: {meeting_title}",
            CalendarEvent.event_type == "meeting"
        ).first()
        
        if event_to_delete:
            db.delete(event_to_delete)
            db.commit()
            return True
        
        return False
    except Exception as e:
        db.rollback()
        raise e