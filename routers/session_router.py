from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db, Module, Session as SessionModel, Resource, SessionContent, Attendance, Admin, Presenter
from auth import get_current_admin_or_presenter, get_current_presenter
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["session_management"])

# Import logging functions
from main import log_admin_action, log_presenter_action

class SessionCreate(BaseModel):
    module_id: int
    session_number: int = Field(..., ge=1, le=10)
    session_type: str = Field(default="Live Session")
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10)
    scheduled_date: Optional[str] = Field(None, description="dd-mm-yyyy")
    scheduled_time: Optional[str] = Field(None, description="--:--")
    duration_minutes: int = Field(default=60, ge=30, le=480)
    meeting_link: Optional[str] = None
    
    @validator('scheduled_date', pre=True)
    def validate_scheduled_date(cls, v):
        if v and v.strip():
            try:
                datetime.strptime(v, '%d-%m-%Y')
                return v
            except ValueError:
                raise ValueError('Date must be in dd-mm-yyyy format')
        return v
    
    @validator('scheduled_time', pre=True)
    def validate_scheduled_time(cls, v):
        if v and v.strip():
            try:
                datetime.strptime(v, '%H:%M')
                return v
            except ValueError:
                raise ValueError('Time must be in HH:MM format')
        return v

class SessionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, min_length=10)
    scheduled_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=30, le=480)
    zoom_link: Optional[str] = None
    recording_url: Optional[str] = None
    syllabus_content: Optional[str] = None

@router.post("/sessions")
async def create_session(
    session_data: SessionCreate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        module = db.query(Module).filter(Module.id == session_data.module_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        
        scheduled_datetime = None
        if session_data.scheduled_date and session_data.scheduled_time:
            try:
                date_str = f"{session_data.scheduled_date} {session_data.scheduled_time}"
                scheduled_datetime = datetime.strptime(date_str, '%d-%m-%Y %H:%M')
            except ValueError:
                logger.warning(f"Invalid date/time format: {session_data.scheduled_date} {session_data.scheduled_time}")
        
        session = SessionModel(
            module_id=session_data.module_id,
            session_number=session_data.session_number,
            title=session_data.title,
            description=session_data.description,
            scheduled_time=scheduled_datetime,
            duration_minutes=session_data.duration_minutes,
            zoom_link=session_data.meeting_link
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        # Log session creation
        if hasattr(current_user, 'username') and db.query(Admin).filter(Admin.id == current_user.id).first():
            log_admin_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action_type="CREATE",
                resource_type="SESSION",
                resource_id=session.id,
                details=f"Created session: {session_data.title}"
            )
        elif hasattr(current_user, 'username') and db.query(Presenter).filter(Presenter.id == current_user.id).first():
            log_presenter_action(
                presenter_id=current_user.id,
                presenter_username=current_user.username,
                action_type="CREATE",
                resource_type="SESSION",
                resource_id=session.id,
                details=f"Created session: {session_data.title}"
            )
        
        return {"message": "Session created successfully", "session_id": session.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create session error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

@router.get("/session/{session_id}")
async def get_session(
    session_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        module = db.query(Module).filter(Module.id == session.module_id).first()
        resources_count = db.query(Resource).filter(Resource.session_id == session.id).count()
        session_content_count = db.query(SessionContent).filter(SessionContent.session_id == session.id).count()
        
        return {
            "id": session.id,
            "module_id": session.module_id,
            "module_title": module.title if module else None,
            "session_number": session.session_number,
            "title": session.title,
            "description": session.description,
            "scheduled_time": session.scheduled_time,
            "duration_minutes": session.duration_minutes,
            "zoom_link": session.zoom_link,
            "recording_url": session.recording_url,
            "syllabus_content": session.syllabus_content,
            "resources_count": resources_count + session_content_count,
            "created_at": session.created_at
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get session error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch session")

@router.get("/sessions")
async def get_module_sessions(
    module_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        sessions = db.query(SessionModel).filter(SessionModel.module_id == module_id).order_by(SessionModel.session_number).all()
        
        result = []
        for session in sessions:
            resources_count = db.query(Resource).filter(Resource.session_id == session.id).count()
            session_content_count = db.query(SessionContent).filter(SessionContent.session_id == session.id).count()
            total_resources_count = resources_count + session_content_count
            attendance_count = db.query(Attendance).filter(Attendance.session_id == session.id).count()
            
            result.append({
                "id": session.id,
                "session_number": session.session_number,
                "title": session.title,
                "description": session.description,
                "scheduled_time": session.scheduled_time,
                "duration_minutes": session.duration_minutes,
                "session_type": getattr(session, 'session_type', 'LIVE'),
                "zoom_link": session.zoom_link,
                "recording_url": session.recording_url,
                "is_completed": getattr(session, 'is_completed', False),
                "resources_count": total_resources_count,
                "attendance_count": attendance_count,
                "syllabus_content": session.syllabus_content,
                "created_at": session.created_at
            })
        
        return result
    except Exception as e:
        logger.error(f"Get module sessions error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch sessions")

@router.put("/sessions/{session_id}")
async def update_session(
    session_id: int,
    session_data: SessionUpdate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        update_data = session_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(session, field, value)
        
        db.commit()
        
        # Log session update
        if hasattr(current_user, 'username') and db.query(Admin).filter(Admin.id == current_user.id).first():
            log_admin_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action_type="UPDATE",
                resource_type="SESSION",
                resource_id=session_id,
                details=f"Updated session: {session.title}"
            )
        elif hasattr(current_user, 'username') and db.query(Presenter).filter(Presenter.id == current_user.id).first():
            log_presenter_action(
                presenter_id=current_user.id,
                presenter_username=current_user.username,
                action_type="UPDATE",
                resource_type="SESSION",
                resource_id=session_id,
                details=f"Updated session: {session.title}"
            )
        
        return {"message": "Session updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update session error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update session")

@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_title = session.title
        db.delete(session)
        db.commit()
        
        # Log session deletion
        if hasattr(current_user, 'username') and db.query(Admin).filter(Admin.id == current_user.id).first():
            log_admin_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action_type="DELETE",
                resource_type="SESSION",
                resource_id=session_id,
                details=f"Deleted session: {session_title}"
            )
        elif hasattr(current_user, 'username') and db.query(Presenter).filter(Presenter.id == current_user.id).first():
            log_presenter_action(
                presenter_id=current_user.id,
                presenter_username=current_user.username,
                action_type="DELETE",
                resource_type="SESSION",
                resource_id=session_id,
                details=f"Deleted session: {session_title}"
            )
        
        return {"message": "Session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete session error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete session")

# Presenter session endpoints
presenter_router = APIRouter(prefix="/presenter", tags=["presenter_sessions"])

@presenter_router.post("/sessions")
async def create_presenter_session(
    session_data: SessionCreate,
    current_presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    try:
        module = db.query(Module).filter(Module.id == session_data.module_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        
        scheduled_datetime = None
        if session_data.scheduled_date and session_data.scheduled_time:
            try:
                date_str = f"{session_data.scheduled_date} {session_data.scheduled_time}"
                scheduled_datetime = datetime.strptime(date_str, '%d-%m-%Y %H:%M')
            except ValueError:
                logger.warning(f"Invalid date/time format: {session_data.scheduled_date} {session_data.scheduled_time}")
        
        session = SessionModel(
            module_id=session_data.module_id,
            session_number=session_data.session_number,
            title=session_data.title,
            description=session_data.description,
            scheduled_time=scheduled_datetime,
            duration_minutes=session_data.duration_minutes,
            zoom_link=session_data.meeting_link
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        log_presenter_action(
            presenter_id=current_presenter.id,
            presenter_username=current_presenter.username,
            action_type="CREATE",
            resource_type="SESSION",
            resource_id=session.id,
            details=f"Created session: {session_data.title}"
        )
        
        return {"message": "Session created successfully", "session_id": session.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create presenter session error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

# Include presenter router in the main router
router.include_router(presenter_router)