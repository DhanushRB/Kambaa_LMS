from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from database import get_db
from session_meeting_service import create_session_meeting, get_session_meetings, update_session_meeting, delete_session_meeting
from auth import get_current_admin_presenter_mentor_or_manager

router = APIRouter(prefix="/session-meetings", tags=["Session Meetings"])

class SessionMeetingCreate(BaseModel):
    session_id: int
    title: str
    meeting_url: str
    description: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    duration_minutes: int = 60

class SessionMeetingUpdate(BaseModel):
    title: Optional[str] = None
    meeting_url: Optional[str] = None
    description: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None

@router.post("/create")
def create_meeting(
    meeting_data: SessionMeetingCreate, 
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Create session meeting with automatic calendar blocking"""
    try:
        # Determine user type
        from database import Admin, Presenter, Mentor, Manager
        user_type = "Admin"
        if db.query(Presenter).filter(Presenter.id == current_user.id).first():
            user_type = "Presenter"
        elif db.query(Mentor).filter(Mentor.id == current_user.id).first():
            user_type = "Mentor"
        elif db.query(Manager).filter(Manager.id == current_user.id).first():
            user_type = "Manager"
        
        meeting = create_session_meeting(
            db=db,
            session_id=meeting_data.session_id,
            title=meeting_data.title,
            meeting_url=meeting_data.meeting_url,
            description=meeting_data.description,
            scheduled_time=meeting_data.scheduled_time,
            duration_minutes=meeting_data.duration_minutes,
            created_by=current_user.id,
            user_type=user_type
        )
        
        message = "Meeting created successfully"
        if meeting_data.scheduled_time:
            message += " and calendar blocked"
            
        return {"message": message, "meeting_id": meeting.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create meeting: {str(e)}")

@router.put("/update/{meeting_id}")
def update_meeting(
    meeting_id: int,
    meeting_data: SessionMeetingUpdate,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Update session meeting with calendar block update"""
    try:
        meeting = update_session_meeting(
            db=db,
            meeting_id=meeting_id,
            title=meeting_data.title,
            meeting_url=meeting_data.meeting_url,
            description=meeting_data.description,
            scheduled_time=meeting_data.scheduled_time,
            duration_minutes=meeting_data.duration_minutes
        )
        
        return {"message": "Meeting updated successfully", "meeting_id": meeting.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update meeting: {str(e)}")

@router.delete("/delete/{meeting_id}")
def delete_meeting(
    meeting_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Delete session meeting and its calendar block"""
    try:
        delete_session_meeting(db, meeting_id)
        return {"message": "Meeting and calendar block deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete meeting: {str(e)}")

@router.get("/session/{session_id}")
def get_meetings_by_session(session_id: int, db: Session = Depends(get_db)):
    """Get all meetings for a session"""
    meetings = get_session_meetings(db, session_id)
    return meetings