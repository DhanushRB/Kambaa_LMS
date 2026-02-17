from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from database import get_db
from auth import get_current_admin_presenter_mentor_or_manager
from session_blocking_service import (
    create_session_with_blocking, 
    update_session_with_blocking, 
    delete_session_with_blocking,
    get_session_conflicts
)

router = APIRouter(prefix="/sessions", tags=["Sessions with Blocking"])

class SessionCreateWithBlocking(BaseModel):
    module_id: int
    session_number: int
    title: str
    description: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    duration_minutes: int = 120
    zoom_link: Optional[str] = None
    syllabus_content: Optional[str] = None

class SessionUpdateWithBlocking(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    zoom_link: Optional[str] = None
    syllabus_content: Optional[str] = None

@router.post("/create-with-blocking")
async def create_session_with_calendar_blocking(
    session_data: SessionCreateWithBlocking,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Create session with automatic calendar blocking"""
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
        
        session = create_session_with_blocking(
            db=db,
            module_id=session_data.module_id,
            session_number=session_data.session_number,
            title=session_data.title,
            description=session_data.description,
            scheduled_time=session_data.scheduled_time,
            duration_minutes=session_data.duration_minutes,
            zoom_link=session_data.zoom_link,
            syllabus_content=session_data.syllabus_content,
            created_by=current_user.id,
            user_type=user_type
        )
        
        message = "Session created successfully"
        if session_data.scheduled_time:
            message += " and calendar blocked"
            
        return {
            "message": message, 
            "session_id": session.id,
            "scheduled_time": session.scheduled_time,
            "calendar_blocked": session.scheduled_time is not None
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

@router.put("/update-with-blocking/{session_id}")
async def update_session_with_calendar_blocking(
    session_id: int,
    session_data: SessionUpdateWithBlocking,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Update session with calendar block management"""
    try:
        session = update_session_with_blocking(
            db=db,
            session_id=session_id,
            title=session_data.title,
            description=session_data.description,
            scheduled_time=session_data.scheduled_time,
            duration_minutes=session_data.duration_minutes,
            zoom_link=session_data.zoom_link,
            syllabus_content=session_data.syllabus_content
        )
        
        return {
            "message": "Session updated successfully",
            "session_id": session.id,
            "scheduled_time": session.scheduled_time,
            "calendar_updated": True
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update session: {str(e)}")

@router.delete("/delete-with-blocking/{session_id}")
async def delete_session_with_calendar_blocking(
    session_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Delete session and its calendar block"""
    try:
        delete_session_with_blocking(db, session_id)
        return {
            "message": "Session and calendar block deleted successfully",
            "session_id": session_id
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")

@router.get("/conflicts/{session_id}")
async def get_session_time_conflicts(
    session_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get potential time conflicts for a session"""
    try:
        conflicts = get_session_conflicts(db, session_id)
        return {
            "session_id": session_id,
            "conflicts": conflicts,
            "has_conflicts": len(conflicts) > 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conflicts: {str(e)}")

@router.post("/reschedule/{session_id}")
async def reschedule_session_with_blocking(
    session_id: int,
    new_time: datetime,
    duration_minutes: Optional[int] = None,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Reschedule session with automatic calendar block update"""
    try:
        session = update_session_with_blocking(
            db=db,
            session_id=session_id,
            scheduled_time=new_time,
            duration_minutes=duration_minutes
        )
        
        return {
            "message": "Session rescheduled successfully",
            "session_id": session.id,
            "old_time": None,  # Could track this if needed
            "new_time": session.scheduled_time,
            "calendar_updated": True
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reschedule session: {str(e)}")

@router.post("/bulk-schedule")
async def bulk_schedule_sessions(
    sessions: list[dict],
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Bulk schedule multiple sessions with conflict checking"""
    try:
        results = []
        conflicts = []
        
        # Determine user type
        from database import Admin, Presenter, Mentor, Manager
        user_type = "Admin"
        if db.query(Presenter).filter(Presenter.id == current_user.id).first():
            user_type = "Presenter"
        elif db.query(Mentor).filter(Mentor.id == current_user.id).first():
            user_type = "Mentor"
        elif db.query(Manager).filter(Manager.id == current_user.id).first():
            user_type = "Manager"
        
        for session_data in sessions:
            try:
                session = create_session_with_blocking(
                    db=db,
                    module_id=session_data['module_id'],
                    session_number=session_data['session_number'],
                    title=session_data['title'],
                    description=session_data.get('description'),
                    scheduled_time=datetime.fromisoformat(session_data['scheduled_time']) if session_data.get('scheduled_time') else None,
                    duration_minutes=session_data.get('duration_minutes', 120),
                    zoom_link=session_data.get('zoom_link'),
                    syllabus_content=session_data.get('syllabus_content'),
                    created_by=current_user.id,
                    user_type=user_type
                )
                
                results.append({
                    "session_id": session.id,
                    "title": session.title,
                    "scheduled_time": session.scheduled_time,
                    "status": "created"
                })
            except ValueError as e:
                conflicts.append({
                    "title": session_data['title'],
                    "scheduled_time": session_data.get('scheduled_time'),
                    "error": str(e)
                })
        
        return {
            "message": f"Bulk scheduling completed: {len(results)} created, {len(conflicts)} conflicts",
            "created_sessions": results,
            "conflicts": conflicts,
            "total_processed": len(sessions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk schedule sessions: {str(e)}")