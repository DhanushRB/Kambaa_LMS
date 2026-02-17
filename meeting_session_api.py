from fastapi import APIRouter, HTTPException, Depends, Form
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from database import get_db, SessionContent
from auth import get_current_user
from meeting_calendar_service import create_meeting_calendar_event

router = APIRouter()

@router.post("/admin/session-content/meeting")
async def create_meeting_content(
    session_id: int = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    meeting_url: str = Form(...),
    scheduled_time: Optional[str] = Form(None),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create meeting content and automatically add to calendar if scheduled
    """
    try:
        # Parse scheduled time if provided
        scheduled_datetime = None
        if scheduled_time:
            try:
                scheduled_datetime = datetime.fromisoformat(scheduled_time.replace('Z', ''))
            except:
                pass
        
        # Create session content
        meeting_content = SessionContent(
            session_id=session_id,
            content_type="MEETING_LINK",
            title=title,
            description=description,
            meeting_url=meeting_url,
            scheduled_time=scheduled_datetime,
            uploaded_by=current_user.id
        )
        
        db.add(meeting_content)
        db.flush()
        
        # Auto-create calendar event if scheduled
        calendar_event_id = None
        if scheduled_datetime:
            calendar_event_id = create_meeting_calendar_event(
                db=db,
                meeting_title=title,
                meeting_description=description,
                meeting_url=meeting_url,
                scheduled_time=scheduled_datetime,
                created_by_id=current_user.id
            )
        
        db.commit()
        
        return {
            "message": "Meeting created successfully",
            "meeting_id": meeting_content.id,
            "calendar_event_created": calendar_event_id is not None,
            "calendar_event_id": calendar_event_id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create meeting: {str(e)}")

@router.put("/admin/session-content/meeting/{content_id}")
async def update_meeting_content(
    content_id: int,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    meeting_url: str = Form(...),
    scheduled_time: Optional[str] = Form(None),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update meeting content and sync with calendar
    """
    try:
        # Get existing meeting content
        meeting_content = db.query(SessionContent).filter(
            SessionContent.id == content_id,
            SessionContent.content_type == "MEETING_LINK"
        ).first()
        
        if not meeting_content:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        original_title = meeting_content.title
        
        # Parse new scheduled time
        scheduled_datetime = None
        if scheduled_time:
            try:
                scheduled_datetime = datetime.fromisoformat(scheduled_time.replace('Z', ''))
            except:
                pass
        
        # Update meeting content
        meeting_content.title = title
        meeting_content.description = description
        meeting_content.meeting_url = meeting_url
        meeting_content.scheduled_time = scheduled_datetime
        
        # Update calendar event if scheduled time exists
        if scheduled_datetime:
            from meeting_calendar_service import update_meeting_calendar_event
            update_meeting_calendar_event(
                db=db,
                meeting_title=title,
                meeting_description=description,
                meeting_url=meeting_url,
                scheduled_time=scheduled_datetime,
                original_title=original_title
            )
        
        db.commit()
        
        return {"message": "Meeting updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update meeting: {str(e)}")

@router.delete("/admin/session-content/meeting/{content_id}")
async def delete_meeting_content(
    content_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete meeting content and remove from calendar
    """
    try:
        # Get meeting content
        meeting_content = db.query(SessionContent).filter(
            SessionContent.id == content_id,
            SessionContent.content_type == "MEETING_LINK"
        ).first()
        
        if not meeting_content:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        meeting_title = meeting_content.title
        
        # Delete meeting content
        db.delete(meeting_content)
        
        # Remove from calendar
        from meeting_calendar_service import delete_meeting_calendar_event
        delete_meeting_calendar_event(db=db, meeting_title=meeting_title)
        
        db.commit()
        
        return {"message": "Meeting deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete meeting: {str(e)}")