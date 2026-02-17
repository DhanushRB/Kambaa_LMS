from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db, Course, Module, SessionModel, Resource, SessionContent, Admin, Presenter
from auth import get_current_admin_or_presenter
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["module_management"])

# Import logging functions from a lightweight utility to avoid circular imports
from logging_utils import log_admin_action, log_presenter_action

class ModuleCreate(BaseModel):
    course_id: int
    week_number: int = Field(..., ge=1, le=52)
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class ModuleUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, min_length=10)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

@router.get("/course/{course_id}")
async def get_course(
    course_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        return {
            "id": course.id,
            "title": course.title,
            "description": course.description,
            "created_at": course.created_at
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get course error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch course")

@router.get("/module/{module_id}")
async def get_module(
    module_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        module = db.query(Module).filter(Module.id == module_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        
        return {
            "id": module.id,
            "course_id": module.course_id,
            "week_number": module.week_number,
            "title": module.title,
            "description": module.description,
            "start_date": module.start_date,
            "end_date": module.end_date,
            "created_at": module.created_at
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get module error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch module")

@router.get("/modules")
async def get_course_modules(
    course_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        modules = db.query(Module).filter(Module.course_id == course_id).order_by(Module.week_number).all()
        
        result = []
        for module in modules:
            sessions = db.query(SessionModel).filter(SessionModel.module_id == module.id).order_by(SessionModel.session_number).all()
            
            total_resources = sum([
                db.query(Resource).filter(Resource.session_id == s.id).count() + 
                db.query(SessionContent).filter(SessionContent.session_id == s.id).count()
                for s in sessions
            ])
            
            result.append({
                "id": module.id,
                "week_number": module.week_number,
                "title": module.title,
                "description": module.description,
                "start_date": module.start_date,
                "end_date": module.end_date,
                "sessions_count": len(sessions),
                "resources_count": total_resources,
                "created_at": module.created_at,
                "sessions": [{
                    "id": s.id,
                    "session_number": s.session_number,
                    "title": s.title,
                    "scheduled_time": s.scheduled_time,
                    "duration_minutes": s.duration_minutes,
                    "session_type": getattr(s, 'session_type', 'LIVE'),
                    "is_completed": getattr(s, 'is_completed', False),
                    "has_recording": bool(s.recording_url)
                } for s in sessions]
            })
        
        return {"modules": result}
    except Exception as e:
        logger.error(f"Get course modules error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch modules")

@router.post("/modules")
async def create_module(
    module_data: ModuleCreate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        course = db.query(Course).filter(Course.id == module_data.course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        module = Module(**module_data.dict())
        db.add(module)
        db.commit()
        db.refresh(module)
        
        # Log module creation
        if hasattr(current_user, 'username') and db.query(Admin).filter(Admin.id == current_user.id).first():
            log_admin_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action_type="CREATE",
                resource_type="MODULE",
                resource_id=module.id,
                details=f"Created module: {module_data.title}"
            )
        elif hasattr(current_user, 'username') and db.query(Presenter).filter(Presenter.id == current_user.id).first():
            log_presenter_action(
                presenter_id=current_user.id,
                presenter_username=current_user.username,
                action_type="CREATE",
                resource_type="MODULE",
                resource_id=module.id,
                details=f"Created module: {module_data.title}"
            )
        
        return {"message": "Module created successfully", "module_id": module.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create module error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create module")

@router.put("/modules/{module_id}")
async def update_module(
    module_id: int,
    module_data: ModuleUpdate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        module = db.query(Module).filter(Module.id == module_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        
        update_data = module_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(module, field, value)
        
        db.commit()
        
        # Log module update
        if hasattr(current_user, 'username') and db.query(Admin).filter(Admin.id == current_user.id).first():
            log_admin_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action_type="UPDATE",
                resource_type="MODULE",
                resource_id=module_id,
                details=f"Updated module: {module.title}"
            )
        elif hasattr(current_user, 'username') and db.query(Presenter).filter(Presenter.id == current_user.id).first():
            log_presenter_action(
                presenter_id=current_user.id,
                presenter_username=current_user.username,
                action_type="UPDATE",
                resource_type="MODULE",
                resource_id=module_id,
                details=f"Updated module: {module.title}"
            )
        
        return {"message": "Module updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update module error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update module")

@router.delete("/modules/{module_id}")
async def delete_module(
    module_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        module = db.query(Module).filter(Module.id == module_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        
        module_title = module.title
        
        db.delete(module)
        db.commit()
        
        # Log module deletion
        if hasattr(current_user, 'username') and db.query(Admin).filter(Admin.id == current_user.id).first():
            log_admin_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action_type="DELETE",
                resource_type="MODULE",
                resource_id=module_id,
                details=f"Deleted module: {module_title}"
            )
        elif hasattr(current_user, 'username') and db.query(Presenter).filter(Presenter.id == current_user.id).first():
            log_presenter_action(
                presenter_id=current_user.id,
                presenter_username=current_user.username,
                action_type="DELETE",
                resource_type="MODULE",
                resource_id=module_id,
                details=f"Deleted module: {module_title}"
            )
        
        return {"message": "Module deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete module error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete module")