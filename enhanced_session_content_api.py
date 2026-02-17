from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional
from database import get_db, SessionContent, CalendarEvent, Session
from auth import get_current_admin_or_presenter
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Session Content"])

class SessionContentCreate(BaseModel):
    session_id: int
    content_type: str  # VIDEO, QUIZ, MATERIAL, MEETING_LINK
    title: str
    description: Optional[str] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = 0
    meeting_url: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    duration_minutes: Optional[int] = 60

@router.post("/session-content/create")
def create_session_content_with_calendar(
    content_data: SessionContentCreate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Create session content and automatically map meetings to calendar for both regular and cohort sessions"""
    try:
        from cohort_specific_models import CohortSessionContent, CohortCourseSession
        
        # Check if it's a cohort session
        cohort_session = db.query(CohortCourseSession).filter(CohortCourseSession.id == content_data.session_id).first()
        
        if cohort_session:
            # Create cohort session content
            content = CohortSessionContent(
                session_id=content_data.session_id,
                content_type=content_data.content_type,
                title=content_data.title,
                description=content_data.description,
                file_path=content_data.file_path,
                file_type=content_data.file_type,
                file_size=content_data.file_size,
                meeting_url=content_data.meeting_url,
                scheduled_time=content_data.scheduled_time,
                uploaded_by=current_user.id
            )
        else:
            # Verify regular session exists
            session = db.query(Session).filter(Session.id == content_data.session_id).first()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Create regular session content
            content = SessionContent(
                session_id=content_data.session_id,
                content_type=content_data.content_type,
                title=content_data.title,
                description=content_data.description,
                file_path=content_data.file_path,
                file_type=content_data.file_type,
                file_size=content_data.file_size,
                meeting_url=content_data.meeting_url,
                scheduled_time=content_data.scheduled_time,
                uploaded_by=current_user.id
            )
        
        db.add(content)
        db.flush()  # Get the content ID
        
        # Auto-create calendar event for meeting links with scheduled time
        calendar_mapped = False
        if content_data.content_type == "MEETING_LINK" and content_data.scheduled_time:
            try:
                end_datetime = content_data.scheduled_time + timedelta(minutes=content_data.duration_minutes or 60)
                
                calendar_event = CalendarEvent(
                    title=f"Meeting: {content_data.title}",
                    description=f"AUTO_GENERATED_SESSION_CONTENT_ID:{content.id}|{content_data.description or f'Scheduled meeting: {content_data.title}'}",
                    start_datetime=content_data.scheduled_time,
                    end_datetime=end_datetime,
                    event_type="meeting",
                    location=content_data.meeting_url,
                    is_auto_generated=True,
                    created_by_admin_id=current_user.id,
                    session_meeting_id=None  # Explicitly set to None since this is not from a SessionMeeting
                )
                
                db.add(calendar_event)
                calendar_mapped = True
                logger.info(f"Auto-created calendar event for meeting content: {content_data.title}")
            except Exception as calendar_error:
                logger.warning(f"Failed to create calendar event for meeting: {str(calendar_error)}")
                # Continue without calendar mapping
        
        db.commit()
        
        message = f"{content_data.content_type.replace('_', ' ').title()} created successfully"
        if calendar_mapped:
            message += " and mapped to calendar"
        
        return {
            "message": message,
            "content_id": content.id,
            "calendar_mapped": calendar_mapped
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create session content: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create content")

@router.get("/sessions/{session_id}/content")
def get_session_content_with_calendar_status(
    session_id: int,
    db: Session = Depends(get_db)
):
    """Get session content with calendar mapping status from both regular and cohort sessions"""
    try:
        from cohort_specific_models import CohortSessionContent, CohortCourseSession
        
        result = []
        
        # Check if it's a cohort session first
        cohort_session = db.query(CohortCourseSession).filter(CohortCourseSession.id == session_id).first()
        
        if cohort_session:
            # Get cohort session content
            cohort_contents = db.query(CohortSessionContent).filter(
                CohortSessionContent.session_id == session_id
            ).order_by(CohortSessionContent.created_at.desc()).all()
            
            for content in cohort_contents:
                # Check if this content has a calendar event
                has_calendar_event = False
                if content.content_type == "MEETING_LINK" and content.scheduled_time:
                    calendar_event = db.query(CalendarEvent).filter(
                        CalendarEvent.start_datetime == content.scheduled_time,
                        CalendarEvent.location == content.meeting_url,
                        CalendarEvent.event_type == "meeting"
                    ).first()
                    has_calendar_event = calendar_event is not None
                
                result.append({
                    "id": content.id,
                    "content_type": content.content_type,
                    "title": content.title,
                    "description": content.description,
                    "file_path": content.file_path,
                    "file_type": content.file_type,
                    "file_size": content.file_size,
                    "meeting_url": content.meeting_url,
                    "scheduled_time": content.scheduled_time,
                    "created_at": content.created_at,
                    "has_calendar_event": has_calendar_event,
                    "is_meeting": content.content_type == "MEETING_LINK",
                    "source": "cohort"
                })
        else:
            # Get regular session content
            contents = db.query(SessionContent).filter(SessionContent.session_id == session_id).all()
            
            for content in contents:
                # Check if this content has a calendar event
                has_calendar_event = False
                if content.content_type == "MEETING_LINK" and content.scheduled_time:
                    calendar_event = db.query(CalendarEvent).filter(
                        CalendarEvent.start_datetime == content.scheduled_time,
                        CalendarEvent.location == content.meeting_url,
                        CalendarEvent.event_type == "meeting"
                    ).first()
                    has_calendar_event = calendar_event is not None
                
                result.append({
                    "id": content.id,
                    "content_type": content.content_type,
                    "title": content.title,
                    "description": content.description,
                    "file_path": content.file_path,
                    "file_type": content.file_type,
                    "file_size": content.file_size,
                    "meeting_url": content.meeting_url,
                    "scheduled_time": content.scheduled_time,
                    "created_at": content.created_at,
                    "has_calendar_event": has_calendar_event,
                    "is_meeting": content.content_type == "MEETING_LINK",
                    "source": "regular"
                })
        
        return {"contents": result}
        
    except Exception as e:
        logger.error(f"Failed to get session content: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch content")

@router.post("/session-content/meeting/{content_id}/map-to-calendar")
def map_existing_meeting_to_calendar(
    content_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Manually map an existing meeting content to calendar"""
    try:
        # Get the content
        content = db.query(SessionContent).filter(SessionContent.id == content_id).first()
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")
        
        if content.content_type != "MEETING_LINK":
            raise HTTPException(status_code=400, detail="Content is not a meeting link")
        
        if not content.scheduled_time:
            raise HTTPException(status_code=400, detail="Meeting has no scheduled time")
        
        # Check if calendar event already exists
        existing_event = db.query(CalendarEvent).filter(
            CalendarEvent.start_datetime == content.scheduled_time,
            CalendarEvent.location == content.meeting_url,
            CalendarEvent.event_type == "meeting"
        ).first()
        
        if existing_event:
            return {"message": "Meeting is already mapped to calendar", "calendar_event_id": existing_event.id}
        
        # Create calendar event
        end_datetime = content.scheduled_time + timedelta(minutes=60)  # Default 1 hour
        
        calendar_event = CalendarEvent(
            title=f"Meeting: {content.title}",
            description=content.description or f"Scheduled meeting: {content.title}",
            start_datetime=content.scheduled_time,
            end_datetime=end_datetime,
            event_type="meeting",
            location=content.meeting_url,
            is_auto_generated=True,
            created_by_admin_id=current_user.id
        )
        
        db.add(calendar_event)
        db.commit()
        
        return {
            "message": "Meeting successfully mapped to calendar",
            "calendar_event_id": calendar_event.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to map meeting to calendar: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to map meeting to calendar")

@router.delete("/session-content/meeting/{content_id}")
def delete_session_content_and_calendar(
    content_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Delete session content and associated calendar event if it's a meeting"""
    try:
        # Get the content
        content = db.query(SessionContent).filter(SessionContent.id == content_id).first()
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")
        
        # If it's a meeting with scheduled time, delete the calendar event
        if content.content_type == "MEETING_LINK":
            # Try multiple approaches to find and delete calendar events
            deleted_events = 0
            
            # Approach 1: Look for events with session content ID in description (new format)
            calendar_events = db.query(CalendarEvent).filter(
                CalendarEvent.event_type == "meeting",
                CalendarEvent.description.like(f"%AUTO_GENERATED_SESSION_CONTENT_ID:{content.id}|%")
            ).all()
            
            for event in calendar_events:
                db.delete(event)
                deleted_events += 1
                logger.info(f"Deleted calendar event (new format) for meeting: {content.title}")
            
            # Approach 2: Look for events with old session content ID format
            if deleted_events == 0 and content.scheduled_time:
                calendar_events = db.query(CalendarEvent).filter(
                    CalendarEvent.start_datetime == content.scheduled_time,
                    CalendarEvent.location == content.meeting_url,
                    CalendarEvent.event_type == "meeting",
                    CalendarEvent.description.like(f"%Session Content ID: {content.id}%")
                ).all()
                
                for event in calendar_events:
                    db.delete(event)
                    deleted_events += 1
                    logger.info(f"Deleted calendar event (old format) for meeting: {content.title}")
            
            # Approach 3: Look for events matching time, location and title pattern
            if deleted_events == 0 and content.scheduled_time:
                calendar_events = db.query(CalendarEvent).filter(
                    CalendarEvent.start_datetime == content.scheduled_time,
                    CalendarEvent.location == content.meeting_url,
                    CalendarEvent.event_type == "meeting",
                    CalendarEvent.title.like(f"%{content.title}%")
                ).all()
                
                for event in calendar_events:
                    db.delete(event)
                    deleted_events += 1
                    logger.info(f"Deleted calendar event (title match) for meeting: {content.title}")
            
            # Approach 4: Look for auto-generated events matching time and location
            if deleted_events == 0 and content.scheduled_time:
                calendar_events = db.query(CalendarEvent).filter(
                    CalendarEvent.start_datetime == content.scheduled_time,
                    CalendarEvent.location == content.meeting_url,
                    CalendarEvent.event_type == "meeting",
                    CalendarEvent.is_auto_generated == True
                ).all()
                
                for event in calendar_events:
                    db.delete(event)
                    deleted_events += 1
                    logger.info(f"Deleted calendar event (auto-generated) for meeting: {content.title}")
        
        # Delete the session content
        db.delete(content)
        db.commit()
        
        message = f"{content.content_type.replace('_', ' ').title()} deleted successfully"
        if content.content_type == "MEETING_LINK":
            message += f" and removed {deleted_events} calendar event(s)"
        
        return {"message": message, "deleted_calendar_events": deleted_events}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete session content: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete content")

@router.post("/session-content/cleanup-orphaned-calendar-events")
def cleanup_orphaned_calendar_events(
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Clean up calendar events that no longer have corresponding session content"""
    try:
        # Find all auto-generated meeting calendar events
        calendar_events = db.query(CalendarEvent).filter(
            CalendarEvent.event_type == "meeting",
            CalendarEvent.is_auto_generated == True
        ).all()
        
        deleted_count = 0
        
        for event in calendar_events:
            should_delete = False
            
            # Check if this event has a session content ID in description (new format)
            if "AUTO_GENERATED_SESSION_CONTENT_ID:" in (event.description or ""):
                try:
                    # Extract session content ID from description
                    desc_parts = event.description.split("AUTO_GENERATED_SESSION_CONTENT_ID:")
                    if len(desc_parts) > 1:
                        content_id_part = desc_parts[1].split("|")[0]
                        content_id = int(content_id_part)
                        
                        # Check if session content still exists
                        matching_content = db.query(SessionContent).filter(
                            SessionContent.id == content_id,
                            SessionContent.content_type == "MEETING_LINK"
                        ).first()
                        
                        if not matching_content:
                            should_delete = True
                except:
                    # If we can't parse the ID, check by other criteria
                    should_delete = True
            else:
                # For events without the new format, check by time and location
                matching_content = db.query(SessionContent).filter(
                    SessionContent.content_type == "MEETING_LINK",
                    SessionContent.scheduled_time == event.start_datetime,
                    SessionContent.meeting_url == event.location
                ).first()
                
                if not matching_content:
                    should_delete = True
            
            # Delete the event if no matching content found
            if should_delete:
                db.delete(event)
                deleted_count += 1
                logger.info(f"Deleted orphaned calendar event: {event.title}")
        
        db.commit()
        
        return {
            "message": f"Cleanup completed. Removed {deleted_count} orphaned calendar events.",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to cleanup orphaned calendar events: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cleanup orphaned calendar events")