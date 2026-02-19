# Cohort-specific Course Management Endpoints

from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_
from database import get_db, Course, CohortCourse, Cohort, UserCohort, Module, Session as SessionModel
from auth import get_current_admin_or_presenter, get_current_admin_presenter_mentor_or_manager
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from email_utils import send_course_added_notification

class CohortCourseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    duration_weeks: Optional[int] = 12
    sessions_per_week: Optional[int] = 2
    is_active: Optional[bool] = True
    banner_image: Optional[str] = None

async def create_cohort_course(
    cohort_id: int,
    course_data: CohortCourseCreate,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Create a course specifically for a cohort"""
    try:
        # Validate input
        if not course_data.title or len(course_data.title.strip()) < 3:
            raise HTTPException(status_code=422, detail="Title must be at least 3 characters")
        
        # Set defaults
        duration_weeks = course_data.duration_weeks or 12
        sessions_per_week = course_data.sessions_per_week or 2
        is_active = course_data.is_active if course_data.is_active is not None else True
        
        # Verify cohort exists
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Create the course
        course = Course(
            title=course_data.title.strip(),
            description=course_data.description,
            duration_weeks=duration_weeks,
            sessions_per_week=sessions_per_week,
            is_active=is_active,
            banner_image=course_data.banner_image,
            created_at=datetime.utcnow()
        )
        db.add(course)
        db.flush()  # Get the course ID
        
        # Assign course to cohort
        cohort_course = CohortCourse(
            cohort_id=cohort_id,
            course_id=course.id,
            assigned_by=current_user["id"]
        )
        db.add(cohort_course)
        
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
            "message": "Course created and assigned to cohort successfully",
            "course_id": course.id,
            "title": course.title,
            "cohort_id": cohort_id
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create cohort course: {str(e)}")

async def get_cohort_courses(
    cohort_id: int,
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get courses assigned to a specific cohort"""
    try:
        # Verify cohort exists
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Get courses assigned to this cohort
        query = db.query(Course).join(CohortCourse).filter(CohortCourse.cohort_id == cohort_id)
        
        if search:
            query = query.filter(
                Course.title.contains(search) | 
                Course.description.contains(search)
            )
        
        total = query.count()
        courses = query.offset((page - 1) * limit).limit(limit).all()
        
        result = []
        for course in courses:
            # Get modules count
            modules_count = db.query(Module).filter(Module.course_id == course.id).count()
            
            # Get assignment info
            cohort_course = db.query(CohortCourse).filter(
                and_(CohortCourse.cohort_id == cohort_id, CohortCourse.course_id == course.id)
            ).first()
            
            result.append({
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "duration_weeks": course.duration_weeks,
                "sessions_per_week": course.sessions_per_week,
                "is_active": course.is_active,
                "banner_image": course.banner_image,
                "modules_count": modules_count,
                "assigned_at": cohort_course.assigned_at if cohort_course else None,
                "created_at": course.created_at,
                "is_cohort_specific": True
            })
        
        return {
            "courses": result,
            "total": total,
            "page": page,
            "limit": limit,
            "cohort_id": cohort_id,
            "cohort_name": cohort.name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch cohort courses: {str(e)}")

async def get_cohort_course_details(
    cohort_id: int,
    course_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get details of a specific course within a cohort"""
    try:
        # Verify cohort exists
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Verify course is assigned to this cohort
        cohort_course = db.query(CohortCourse).filter(
            and_(CohortCourse.cohort_id == cohort_id, CohortCourse.course_id == course_id)
        ).first()
        
        if not cohort_course:
            raise HTTPException(status_code=404, detail="Course not found in this cohort")
        
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Get modules
        modules = db.query(Module).filter(Module.course_id == course_id).order_by(Module.week_number).all()
        
        modules_data = []
        for module in modules:
            sessions = db.query(SessionModel).filter(SessionModel.module_id == module.id).all()
            modules_data.append({
                "id": module.id,
                "week_number": module.week_number,
                "title": module.title,
                "description": module.description,
                "start_date": module.start_date,
                "end_date": module.end_date,
                "sessions_count": len(sessions),
                "created_at": module.created_at
            })
        
        return {
            "id": course.id,
            "title": course.title,
            "description": course.description,
            "duration_weeks": course.duration_weeks,
            "sessions_per_week": course.sessions_per_week,
            "is_active": course.is_active,
            "banner_image": course.banner_image,
            "created_at": course.created_at,
            "assigned_at": cohort_course.assigned_at,
            "cohort_id": cohort_id,
            "cohort_name": cohort.name,
            "modules": modules_data,
            "is_cohort_specific": True
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch course details: {str(e)}")

async def update_cohort_course(
    cohort_id: int,
    course_id: int,
    course_data: CohortCourseCreate,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Update a course within a cohort"""
    try:
        # Verify cohort exists
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Verify course is assigned to this cohort
        cohort_course = db.query(CohortCourse).filter(
            and_(CohortCourse.cohort_id == cohort_id, CohortCourse.course_id == course_id)
        ).first()
        
        if not cohort_course:
            raise HTTPException(status_code=404, detail="Course not found in this cohort")
        
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Update course
        course.title = course_data.title
        course.description = course_data.description
        course.duration_weeks = course_data.duration_weeks
        course.sessions_per_week = course_data.sessions_per_week
        course.is_active = course_data.is_active
        course.banner_image = course_data.banner_image
        
        db.commit()
        
        return {
            "message": "Course updated successfully",
            "course_id": course.id,
            "cohort_id": cohort_id
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update course: {str(e)}")

async def delete_cohort_course(
    cohort_id: int,
    course_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Delete a course from a cohort (removes assignment, doesn't delete course if used elsewhere)"""
    try:
        # Verify cohort exists
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Verify course is assigned to this cohort
        cohort_course = db.query(CohortCourse).filter(
            and_(CohortCourse.cohort_id == cohort_id, CohortCourse.course_id == course_id)
        ).first()
        
        if not cohort_course:
            raise HTTPException(status_code=404, detail="Course not found in this cohort")
        
        # Check if course is used in other cohorts
        other_assignments = db.query(CohortCourse).filter(
            and_(CohortCourse.course_id == course_id, CohortCourse.cohort_id != cohort_id)
        ).count()
        
        # Remove from cohort
        db.delete(cohort_course)
        
        # If course is not used in other cohorts, delete the course entirely
        if other_assignments == 0:
            course = db.query(Course).filter(Course.id == course_id).first()
            if course:
                # Delete related modules and sessions first
                modules = db.query(Module).filter(Module.course_id == course_id).all()
                for module in modules:
                    db.query(SessionModel).filter(SessionModel.module_id == module.id).delete()
                    db.delete(module)
                
                db.delete(course)
        
        db.commit()
        
        return {
            "message": "Course removed from cohort successfully",
            "course_id": course_id,
            "cohort_id": cohort_id,
            "fully_deleted": other_assignments == 0
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete course: {str(e)}")

async def check_cohort_access(
    cohort_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Check if current user has access to manage courses in this cohort"""
    try:
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Admin and Manager have access to all cohorts
        # Presenters need to be assigned to the cohort (this can be extended later)
        return {
            "has_access": True,
            "cohort_id": cohort_id,
            "cohort_name": cohort.name,
            "user_role": current_user.get("role", "Admin")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check access: {str(e)}")