from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import datetime
from pydantic import BaseModel

from database import get_db, Cohort
from auth import get_current_admin_presenter_mentor_or_manager
from cohort_specific_models import (
    CohortSpecificCourse, 
    CohortCourseModule, 
    CohortCourseSession,
    CohortCourseResource
)
from email_utils import send_course_added_notification

router = APIRouter(prefix="/cohorts", tags=["Cohort Courses"])

class CohortCourseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    num_modules: int = 12
    sessions_per_module: int = 2
    is_active: bool = True
    banner_image: Optional[str] = None

class CohortCourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    num_modules: Optional[int] = None
    sessions_per_module: Optional[int] = None
    is_active: Optional[bool] = None
    banner_image: Optional[str] = None

class CohortCourseModuleUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

@router.post("/{cohort_id}/courses")
async def create_cohort_course(
    cohort_id: int,
    course_data: CohortCourseCreate,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Create course specifically for a cohort"""
    try:
        # Verify cohort exists
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Create cohort-specific course
        # Map frontend names (num_modules, sessions_per_module) to DB names (duration_weeks, sessions_per_week)
        course = CohortSpecificCourse(
            cohort_id=cohort_id,
            title=course_data.title,
            description=course_data.description,
            duration_weeks=course_data.num_modules,
            sessions_per_week=course_data.sessions_per_module,
            is_active=course_data.is_active,
            banner_image=course_data.banner_image,
            created_by=None  # Set to None to avoid foreign key constraint with presenters
        )
        db.add(course)
        db.flush()
        
        # Auto-setup course structure
        await auto_setup_cohort_course_structure(
            course.id, 
            course_data.num_modules, 
            course_data.sessions_per_module, 
            db
        )
        
        db.commit()
        db.refresh(course)
        
        # Send email notification to cohort students
        await send_course_added_notification(
            db=db,
            cohort_id=cohort_id,
            course_title=course.title,
            course_description=course.description or "",
            duration_weeks=course.duration_weeks,
            sessions_per_week=course.sessions_per_week
        )
        
        return {
            "message": "Cohort course created successfully",
            "course_id": course.id,
            "cohort_id": cohort_id,
            "title": course.title
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create cohort course: {str(e)}")

async def auto_setup_cohort_course_structure(
    course_id: int, 
    duration_weeks: int, 
    sessions_per_week: int, 
    db: Session
):
    """Auto-generate cohort course structure"""
    try:
        for week in range(1, duration_weeks + 1):
            module = CohortCourseModule(
                course_id=course_id,
                week_number=week,
                title=f"Week {week} - Module",
                description=f"Learning objectives and content for week {week}"
            )
            db.add(module)
            db.flush()
            
            for session_num in range(1, sessions_per_week + 1):
                session = CohortCourseSession(
                    module_id=module.id,
                    session_number=session_num,
                    title=f"Week {week} - Session {session_num}",
                    description=f"Session {session_num} content for week {week}",
                    duration_minutes=120
                )
                db.add(session)
        
        db.flush()
    except Exception as e:
        db.rollback()
        raise e

@router.get("/{cohort_id}/courses")
async def get_cohort_courses(
    cohort_id: int,
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get courses created for a specific cohort"""
    try:
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        query = db.query(CohortSpecificCourse).filter(CohortSpecificCourse.cohort_id == cohort_id)
        
        if search:
            query = query.filter(
                CohortSpecificCourse.title.contains(search) |
                CohortSpecificCourse.description.contains(search)
            )
        
        total = query.count()
        courses = query.offset((page - 1) * limit).limit(limit).all()
        
        result = []
        for course in courses:
            modules_count = db.query(CohortCourseModule).filter(
                CohortCourseModule.course_id == course.id
            ).count()
            
            result.append({
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "num_modules": course.duration_weeks,  # Map duration_weeks back to num_modules
                "sessions_per_module": course.sessions_per_week,  # Map sessions_per_week back to sessions_per_module
                "is_active": course.is_active,
                "banner_image": course.banner_image,
                "modules_count": modules_count,
                "created_at": course.created_at,
                "cohort_id": cohort_id,
                "is_cohort_course": True
            })
        
        return {
            "courses": result,
            "total": total,
            "page": page,
            "limit": limit,
            "cohort_name": cohort.name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch cohort courses: {str(e)}")

# Removed the problematic GET route for course details
# This allows frontend to navigate directly to modules page
# @router.get("/{cohort_id}/courses/{course_id}")
# async def get_cohort_course_details(...)
# Route removed to prevent navigation interception

@router.get("/{cohort_id}/courses/{course_id}")
async def get_cohort_course_details(
    cohort_id: int,
    course_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get details of a specific cohort course"""
    try:
        course = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.id == course_id,
            CohortSpecificCourse.cohort_id == cohort_id
        ).first()
        
        if not course:
            raise HTTPException(status_code=404, detail="Course not found in this cohort")
        
        modules_count = db.query(CohortCourseModule).filter(
            CohortCourseModule.course_id == course_id
        ).count()
        
        return {
            "id": course.id,
            "title": course.title,
            "description": course.description,
            "duration_weeks": course.duration_weeks,
            "sessions_per_week": course.sessions_per_week,
            "is_active": course.is_active,
            "banner_image": course.banner_image,
            "modules_count": modules_count,
            "created_at": course.created_at,
            "cohort_id": cohort_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch course details: {str(e)}")

@router.get("/{cohort_id}/courses/{course_id}/modules/{module_id}")
async def get_cohort_course_module(
    cohort_id: int,
    course_id: int,
    module_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get details of a specific cohort course module"""
    try:
        module = db.query(CohortCourseModule).filter(
            CohortCourseModule.id == module_id,
            CohortCourseModule.course_id == course_id
        ).first()
        
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
            
        return {
            "id": module.id,
            "course_id": module.course_id,
            "week_number": module.week_number,
            "title": module.title,
            "description": module.description,
            "created_at": module.created_at
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch module details: {str(e)}")

@router.put("/{cohort_id}/courses/{course_id}/modules/{module_id}")
async def update_cohort_course_module(
    cohort_id: int,
    course_id: int,
    module_id: int,
    module_data: CohortCourseModuleUpdate,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Update a cohort-specific course module"""
    try:
        module = db.query(CohortCourseModule).filter(
            CohortCourseModule.id == module_id,
            CohortCourseModule.course_id == course_id
        ).first()
        
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        
        update_data = module_data.dict(exclude_unset=True)
        
        # Handle date parsing if needed (assuming strings in format YYYY-MM-DD or ISO)
        if 'start_date' in update_data and update_data['start_date']:
             try:
                 # If it's just a date string, parse it
                 if len(update_data['start_date']) == 10:
                      update_data['start_date'] = datetime.strptime(update_data['start_date'], "%Y-%m-%d")
                 else:
                      update_data['start_date'] = datetime.fromisoformat(update_data['start_date'].replace('Z', '+00:00'))
             except ValueError:
                 pass # Let sqlalchemy handle it or fail

        if 'end_date' in update_data and update_data['end_date']:
             try:
                 if len(update_data['end_date']) == 10:
                      update_data['end_date'] = datetime.strptime(update_data['end_date'], "%Y-%m-%d")
                 else:
                      update_data['end_date'] = datetime.fromisoformat(update_data['end_date'].replace('Z', '+00:00'))
             except ValueError:
                 pass

        for field, value in update_data.items():
            setattr(module, field, value)
        
        db.commit()
        db.refresh(module)
        
        return {
            "message": "Module updated successfully",
            "id": module.id,
            "title": module.title
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update module: {str(e)}")

@router.put("/{cohort_id}/courses/{course_id}")
async def update_cohort_course(
    cohort_id: int,
    course_id: int,
    course_data: CohortCourseUpdate,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Update a cohort-specific course"""
    try:
        course = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.id == course_id,
            CohortSpecificCourse.cohort_id == cohort_id
        ).first()
        
        if not course:
            raise HTTPException(status_code=404, detail="Course not found in this cohort")
        
        update_data = course_data.dict(exclude_unset=True)
        
        # Map frontend field names to database field names
        if 'num_modules' in update_data:
            update_data['duration_weeks'] = update_data.pop('num_modules')
        if 'sessions_per_module' in update_data:
            update_data['sessions_per_week'] = update_data.pop('sessions_per_module')
            
        for field, value in update_data.items():
            if hasattr(course, field):
                setattr(course, field, value)
        
        db.commit()
        
        return {"message": "Cohort course updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update course: {str(e)}")

@router.delete("/{cohort_id}/courses/{course_id}")
async def delete_cohort_course(
    cohort_id: int,
    course_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Delete a cohort-specific course"""
    try:
        course = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.id == course_id,
            CohortSpecificCourse.cohort_id == cohort_id
        ).first()
        
        if not course:
            raise HTTPException(status_code=404, detail="Course not found in this cohort")
        
        # Delete related records in reverse order
        try:
            # Delete enrollments first
            try:
                from cohort_specific_models import CohortSpecificEnrollment
                db.query(CohortSpecificEnrollment).filter(
                    CohortSpecificEnrollment.course_id == course_id
                ).delete(synchronize_session=False)
            except:
                pass  # Table might not exist
            
            # Delete resources first
            modules = db.query(CohortCourseModule).filter(
                CohortCourseModule.course_id == course_id
            ).all()
            
            for module in modules:
                sessions = db.query(CohortCourseSession).filter(
                    CohortCourseSession.module_id == module.id
                ).all()
                
                for session in sessions:
                    # Delete resources
                    db.query(CohortCourseResource).filter(
                        CohortCourseResource.session_id == session.id
                    ).delete(synchronize_session=False)
                    
                    # Delete session contents
                    try:
                        from cohort_specific_models import CohortSessionContent
                        db.query(CohortSessionContent).filter(
                            CohortSessionContent.session_id == session.id
                        ).delete(synchronize_session=False)
                    except:
                        pass  # Table might not exist
                
                # Delete sessions
                db.query(CohortCourseSession).filter(
                    CohortCourseSession.module_id == module.id
                ).delete(synchronize_session=False)
            
            # Delete modules
            db.query(CohortCourseModule).filter(
                CohortCourseModule.course_id == course_id
            ).delete(synchronize_session=False)
            
        except Exception as cleanup_error:
            print(f"Cleanup error: {cleanup_error}")
            # Continue with course deletion even if cleanup fails
        
        # Delete the course
        db.delete(course)
        db.commit()
        
        return {"message": "Cohort course deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete course: {str(e)}")