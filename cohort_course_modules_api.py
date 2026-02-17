from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from database import get_db
from auth import get_current_admin_presenter_mentor_or_manager
from cohort_specific_models import CohortSpecificCourse, CohortCourseModule, CohortCourseSession

router = APIRouter(prefix="/cohorts", tags=["Cohort Course Modules"])

class ModuleCreate(BaseModel):
    title: str
    description: Optional[str] = None
    week_number: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class ModuleUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class SessionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    session_number: Optional[int] = None
    scheduled_time: Optional[str] = None
    duration_minutes: Optional[int] = 120

class SessionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    session_number: Optional[int] = None

@router.get("/{cohort_id}/courses/{course_id}/modules")
async def get_cohort_course_modules(
    cohort_id: int,
    course_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get modules for a cohort course"""
    try:
        course = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.id == course_id,
            CohortSpecificCourse.cohort_id == cohort_id
        ).first()
        
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        modules = db.query(CohortCourseModule).filter(
            CohortCourseModule.course_id == course_id
        ).order_by(CohortCourseModule.week_number).all()
        
        result = []
        for module in modules:
            sessions = db.query(CohortCourseSession).filter(
                CohortCourseSession.module_id == module.id
            ).all()
            
            result.append({
                "id": module.id,
                "week_number": module.week_number,
                "title": module.title,
                "description": module.description,
                "start_date": module.start_date,
                "end_date": module.end_date,
                "sessions_count": len(sessions),
                "created_at": module.created_at
            })
        
        return {"modules": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch modules: {str(e)}")

@router.post("/{cohort_id}/courses/{course_id}/modules")
async def create_cohort_course_module(
    cohort_id: int,
    course_id: int,
    module_data: ModuleCreate,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Create a new module for a cohort course"""
    try:
        course = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.id == course_id,
            CohortSpecificCourse.cohort_id == cohort_id
        ).first()
        
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Auto-assign week number if not provided
        if not module_data.week_number:
            max_week = db.query(CohortCourseModule).filter(
                CohortCourseModule.course_id == course_id
            ).count()
            module_data.week_number = max_week + 1
        
        module = CohortCourseModule(
            course_id=course_id,
            week_number=module_data.week_number,
            title=module_data.title,
            description=module_data.description,
            start_date=module_data.start_date,
            end_date=module_data.end_date
        )
        
        db.add(module)
        db.flush()
        
        # Auto-create sessions for the module
        for session_num in range(1, course.sessions_per_week + 1):
            session = CohortCourseSession(
                module_id=module.id,
                session_number=session_num,
                title=f"{module.title} - Session {session_num}",
                description=f"Session {session_num} content for {module.title}",
                duration_minutes=120
            )
            db.add(session)
        
        db.commit()
        return {"message": "Module created successfully", "module_id": module.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create module: {str(e)}")

@router.put("/{cohort_id}/courses/{course_id}/modules/{module_id}")
async def update_cohort_course_module(
    cohort_id: int,
    course_id: int,
    module_id: int,
    module_data: ModuleUpdate,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Update a cohort course module"""
    try:
        module = db.query(CohortCourseModule).filter(
            CohortCourseModule.id == module_id,
            CohortCourseModule.course_id == course_id
        ).first()
        
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        
        update_data = module_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(module, field, value)
        
        db.commit()
        return {"message": "Module updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update module: {str(e)}")

@router.post("/{cohort_id}/courses/{course_id}/modules/{module_id}/sessions")
async def create_cohort_session(
    cohort_id: int,
    course_id: int,
    module_id: int,
    session_data: SessionCreate,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Create a new session for a cohort course module"""
    try:
        module = db.query(CohortCourseModule).filter(
            CohortCourseModule.id == module_id,
            CohortCourseModule.course_id == course_id
        ).first()
        
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        
        # Determine session number if not provided
        if not session_data.session_number:
            max_session = db.query(CohortCourseSession).filter(
                CohortCourseSession.module_id == module_id
            ).count()
            session_data.session_number = max_session + 1
            
        session = CohortCourseSession(
            module_id=module_id,
            session_number=session_data.session_number,
            title=session_data.title,
            description=session_data.description,
            duration_minutes=session_data.duration_minutes or 120
        )
        
        if session_data.scheduled_time:
            from datetime import datetime
            date_str = session_data.scheduled_time
            if len(date_str) == 10:  # YYYY-MM-DD
                session.scheduled_time = datetime.strptime(date_str + ' 09:00:00', '%Y-%m-%d %H:%M:%S')
            else:
                try:
                    session.scheduled_time = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    pass

        db.add(session)
        db.commit()
        db.refresh(session)
        
        return {"message": "Session created successfully", "session_id": session.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

@router.get("/{cohort_id}/courses/{course_id}/modules/{module_id}/sessions")
async def get_cohort_module_sessions(
    cohort_id: int,
    course_id: int,
    module_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get sessions for a cohort course module"""
    try:
        module = db.query(CohortCourseModule).filter(
            CohortCourseModule.id == module_id,
            CohortCourseModule.course_id == course_id
        ).first()
        
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        
        sessions = db.query(CohortCourseSession).filter(
            CohortCourseSession.module_id == module_id
        ).order_by(CohortCourseSession.session_number).all()
        
        result = []
        for session in sessions:
            result.append({
                "id": session.id,
                "session_number": session.session_number,
                "title": session.title,
                "description": session.description,
                "scheduled_time": session.scheduled_time,
                "duration_minutes": session.duration_minutes,
                "created_at": session.created_at
            })
        
        return {"sessions": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sessions: {str(e)}")

@router.put("/{cohort_id}/courses/{course_id}/modules/{module_id}/sessions/{session_id}")
async def update_cohort_session(
    cohort_id: int,
    course_id: int,
    module_id: int,
    session_id: int,
    session_data: SessionUpdate,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Update a cohort course session"""
    try:
        session = db.query(CohortCourseSession).filter(
            CohortCourseSession.id == session_id,
            CohortCourseSession.module_id == module_id
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        update_data = session_data.dict(exclude_unset=True)
        
        # Handle scheduled_time conversion from date string to datetime
        if 'scheduled_time' in update_data and update_data['scheduled_time']:
            from datetime import datetime
            date_str = update_data['scheduled_time']
            if len(date_str) == 10:  # YYYY-MM-DD format
                update_data['scheduled_time'] = datetime.strptime(date_str + ' 09:00:00', '%Y-%m-%d %H:%M:%S')
        
        for field, value in update_data.items():
            setattr(session, field, value)
        
        db.commit()
        return {"message": "Session updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update session: {str(e)}")

@router.delete("/{cohort_id}/courses/{course_id}/modules/{module_id}")
async def delete_cohort_course_module(
    cohort_id: int,
    course_id: int,
    module_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Delete a cohort course module"""
    try:
        module = db.query(CohortCourseModule).filter(
            CohortCourseModule.id == module_id,
            CohortCourseModule.course_id == course_id
        ).first()
        
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        
        # Delete associated sessions first
        db.query(CohortCourseSession).filter(
            CohortCourseSession.module_id == module_id
        ).delete()
        
        # Delete the module
        db.delete(module)
        db.commit()
        
        return {"message": "Module deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete module: {str(e)}")

@router.delete("/{cohort_id}/courses/{course_id}/modules/{module_id}/sessions/{session_id}")
async def delete_cohort_session(
    cohort_id: int,
    course_id: int,
    module_id: int,
    session_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Delete a cohort course session"""
    try:
        session = db.query(CohortCourseSession).filter(
            CohortCourseSession.id == session_id,
            CohortCourseSession.module_id == module_id
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        db.delete(session)
        db.commit()
        
        return {"message": "Session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")