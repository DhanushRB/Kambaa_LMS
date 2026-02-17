# Presenter Users Endpoints - Cohort-filtered user access

from fastapi import HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from database import get_db, User, Presenter, Cohort, UserCohort, PresenterCohort
from auth import get_current_presenter
from typing import Optional
from email_utils import send_course_added_notification
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/presenter/users")
async def get_presenter_users(
    page: int = 1,
    limit: int = 50,
    search: Optional[str] = None,
    role: Optional[str] = None,
    college: Optional[str] = None,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    """Get users that belong to cohorts assigned to the current presenter"""
    try:
        # Get cohorts assigned to the current presenter
        presenter_cohorts = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == current_presenter.id
        ).all()
        
        if not presenter_cohorts:
            # If presenter has no assigned cohorts, return empty result
            return {
                "users": [],
                "total": 0,
                "page": page,
                "limit": limit
            }
        
        # Get cohort IDs assigned to this presenter
        assigned_cohort_ids = [pc.cohort_id for pc in presenter_cohorts]
        
        # Base query for users in assigned cohorts only
        query = db.query(User).join(UserCohort).filter(
            UserCohort.cohort_id.in_(assigned_cohort_ids),
            User.user_type.in_(['Student', 'Faculty'])
        )
        
        # Apply search filter
        if search:
            query = query.filter(
                or_(
                    User.username.contains(search),
                    User.email.contains(search),
                    User.college.contains(search)
                )
            )
        
        # Apply role filter
        if role:
            query = query.filter(User.user_type == role)
        
        # Apply college filter
        if college:
            query = query.filter(User.college == college)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        users = query.offset((page - 1) * limit).limit(limit).all()
        
        # Format response
        user_list = []
        for user in users:
            user_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "college": user.college,
                "department": user.department,
                "year": user.year,
                "user_type": user.user_type,
                "active": True,
                "created_at": user.created_at
            }
            
            # Add faculty-specific fields if user is faculty
            if user.user_type == 'Faculty':
                user_data.update({
                    "experience": user.experience,
                    "designation": user.designation,
                    "specialization": user.specialization,
                    "employment_type": user.employment_type,
                    "joining_date": user.joining_date
                })
            
            user_list.append(user_data)
        
        return {
            "users": user_list,
            "total": total,
            "page": page,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Get presenter users error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")

@router.get("/presenter/cohorts")
async def get_presenter_cohorts(
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    """Get cohorts assigned to the current presenter"""
    try:
        # Get only cohorts assigned to this presenter
        presenter_cohorts = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == current_presenter.id
        ).all()
        
        cohort_list = []
        for pc in presenter_cohorts:
            cohort = pc.cohort
            # Get user count for each cohort
            user_count = db.query(UserCohort).filter(UserCohort.cohort_id == cohort.id).count()
            
            cohort_list.append({
                "id": cohort.id,
                "name": cohort.name,
                "description": cohort.description,
                "start_date": cohort.start_date,
                "end_date": cohort.end_date,
                "instructor_name": cohort.instructor_name,
                "user_count": user_count,
                "assigned_at": pc.assigned_at,
                "created_at": cohort.created_at
            })
        
        return {"cohorts": cohort_list}
        
    except Exception as e:
        logger.error(f"Get presenter cohorts error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch cohorts")

@router.get("/presenter/cohorts/{cohort_id}")
async def get_presenter_cohort_details(
    cohort_id: int,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific cohort assigned to the presenter"""
    try:
        # Verify presenter has access to this cohort
        presenter_cohort = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == current_presenter.id,
            PresenterCohort.cohort_id == cohort_id
        ).first()
        
        if not presenter_cohort:
            raise HTTPException(status_code=403, detail="Access denied: Cohort not assigned to presenter")
        
        # Get cohort details
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Get users in cohort
        user_cohorts = db.query(UserCohort).filter(UserCohort.cohort_id == cohort_id).all()
        users = [{
            "id": uc.user.id,
            "username": uc.user.username,
            "email": uc.user.email,
            "college_name": uc.user.college,
            "assigned_at": uc.assigned_at
        } for uc in user_cohorts]
        
        # Get cohort courses (both cohort-specific and global courses assigned to cohort)
        from database import CohortCourse, Course
        from cohort_specific_models import CohortSpecificCourse
        
        courses = []
        
        # Get cohort-specific courses
        cohort_specific_courses = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.cohort_id == cohort_id
        ).all()
        
        for csc in cohort_specific_courses:
            courses.append({
                "id": csc.id,
                "title": csc.title,
                "description": csc.description,
                "duration_weeks": csc.duration_weeks,
                "assigned_at": csc.created_at,
                "is_cohort_specific": True,
                "course_type": "Cohort Course"
            })
        
        # Get global courses assigned to cohort
        cohort_courses = db.query(CohortCourse).filter(CohortCourse.cohort_id == cohort_id).all()
        for cc in cohort_courses:
            course = cc.course
            courses.append({
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "duration_weeks": course.duration_weeks,
                "assigned_at": cc.assigned_at,
                "is_cohort_specific": False,
                "course_type": "Global Course"
            })
        
        return {
            "id": cohort.id,
            "name": cohort.name,
            "description": cohort.description,
            "start_date": cohort.start_date,
            "end_date": cohort.end_date,
            "instructor_name": cohort.instructor_name,
            "is_active": cohort.is_active,
            "created_at": cohort.created_at,
            "users": users,
            "courses": courses
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get presenter cohort details error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch cohort details")

from pydantic import BaseModel
from typing import List

class CourseAssignRequest(BaseModel):
    course_ids: List[int]

@router.post("/presenter/cohorts/{cohort_id}/assign-courses")
async def assign_courses_to_presenter_cohort(
    cohort_id: int,
    request_data: CourseAssignRequest,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    """Assign existing global courses to a cohort (presenter access)"""
    try:
        # Verify presenter has access to this cohort
        presenter_cohort = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == current_presenter.id,
            PresenterCohort.cohort_id == cohort_id
        ).first()
        
        if not presenter_cohort:
            raise HTTPException(status_code=403, detail="Access denied: Cohort not assigned to presenter")
        
        # Verify cohort exists
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        from database import Course, CohortCourse
        assigned_courses = []
        errors = []
        
        for course_id in request_data.course_ids:
            # Verify course exists
            course = db.query(Course).filter(Course.id == course_id).first()
            if not course:
                errors.append(f"Course ID {course_id} not found")
                continue
            
            # Check if course is already assigned to cohort
            existing_assignment = db.query(CohortCourse).filter(
                CohortCourse.cohort_id == cohort_id,
                CohortCourse.course_id == course_id
            ).first()
            
            if existing_assignment:
                errors.append(f"Course {course.title} is already assigned to this cohort")
                continue
            
            # Assign course to cohort (set assigned_by to None since presenter IDs don't match admin table)
            cohort_course = CohortCourse(
                cohort_id=cohort_id,
                course_id=course_id,
                assigned_by=None  # Set to None to avoid foreign key constraint
            )
            db.add(cohort_course)
            assigned_courses.append(course.title)
            
            # Send email notification for this course
            await send_course_added_notification(
                db=db,
                cohort_id=cohort_id,
                course_title=course.title,
                course_description=course.description or "",
                duration_weeks=course.duration_weeks or 0,
                sessions_per_week=course.sessions_per_week or 0
            )
        
        db.commit()
        
        return {
            "message": f"Assigned {len(assigned_courses)} courses to cohort",
            "assigned_courses": assigned_courses,
            "errors": errors
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Assign courses to presenter cohort error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to assign courses to cohort")

@router.get("/presenter/cohorts/{cohort_id}/courses/{course_id}")
async def get_presenter_cohort_course(
    cohort_id: int,
    course_id: int,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    """Get details of a specific course in a cohort (presenter access)"""
    try:
        # Verify presenter has access to this cohort
        presenter_cohort = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == current_presenter.id,
            PresenterCohort.cohort_id == cohort_id
        ).first()
        
        if not presenter_cohort:
            raise HTTPException(status_code=403, detail="Access denied: Cohort not assigned to presenter")
        
        from cohort_specific_models import CohortSpecificCourse
        from database import Course, CohortCourse
        
        # Check if it's a cohort-specific course
        cohort_course = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.id == course_id,
            CohortSpecificCourse.cohort_id == cohort_id
        ).first()
        
        if cohort_course:
            return {
                "id": cohort_course.id,
                "title": cohort_course.title,
                "description": cohort_course.description,
                "duration_weeks": cohort_course.duration_weeks,
                "sessions_per_week": cohort_course.sessions_per_week,
                "is_cohort_specific": True,
                "cohort_id": cohort_course.cohort_id
            }
        
        # Check if it's a global course assigned to cohort
        assignment = db.query(CohortCourse).filter(
            CohortCourse.cohort_id == cohort_id,
            CohortCourse.course_id == course_id
        ).first()
        
        if assignment:
            course = assignment.course
            return {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "duration_weeks": course.duration_weeks,
                "sessions_per_week": course.sessions_per_week,
                "is_cohort_specific": False,
                "cohort_id": cohort_id
            }
        
        raise HTTPException(status_code=404, detail="Course not found in cohort")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get presenter cohort course error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch course details")

@router.get("/presenter/cohorts/{cohort_id}/courses/{course_id}/modules")
async def get_presenter_cohort_course_modules(
    cohort_id: int,
    course_id: int,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    """Get modules for a specific course in a cohort (presenter access)"""
    try:
        # Verify presenter has access to this cohort
        presenter_cohort = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == current_presenter.id,
            PresenterCohort.cohort_id == cohort_id
        ).first()
        
        if not presenter_cohort:
            raise HTTPException(status_code=403, detail="Access denied: Cohort not assigned to presenter")
        
        from cohort_specific_models import CohortSpecificCourse, CohortCourseModule
        from database import Course, CohortCourse, Module
        
        modules = []
        
        # Check if it's a cohort-specific course
        cohort_course = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.id == course_id,
            CohortSpecificCourse.cohort_id == cohort_id
        ).first()
        
        if cohort_course:
            # Get cohort-specific modules
            cohort_modules = db.query(CohortCourseModule).filter(
                CohortCourseModule.course_id == course_id
            ).order_by(CohortCourseModule.week_number).all()
            
            for module in cohort_modules:
                # Get session count for cohort modules
                from cohort_specific_models import CohortCourseSession
                session_count = db.query(CohortCourseSession).filter(
                    CohortCourseSession.module_id == module.id
                ).count()
                
                modules.append({
                    "id": module.id,
                    "title": module.title,
                    "description": module.description,
                    "week_number": module.week_number,
                    "start_date": module.start_date,
                    "end_date": module.end_date,
                    "sessions_count": session_count,
                    "is_cohort_specific": True
                })
        else:
            # Check if it's a global course assigned to cohort
            assignment = db.query(CohortCourse).filter(
                CohortCourse.cohort_id == cohort_id,
                CohortCourse.course_id == course_id
            ).first()
            
            if assignment:
                # Get global course modules
                global_modules = db.query(Module).filter(
                    Module.course_id == course_id
                ).order_by(Module.week_number).all()
                
                for module in global_modules:
                    # Get session count for global modules
                    from database import Session as DBSession
                    session_count = db.query(DBSession).filter(
                        DBSession.module_id == module.id
                    ).count()
                    
                    modules.append({
                        "id": module.id,
                        "title": module.title,
                        "description": module.description,
                        "week_number": module.week_number,
                        "start_date": module.start_date,
                        "end_date": module.end_date,
                        "sessions_count": session_count,
                        "is_cohort_specific": False
                    })
            else:
                raise HTTPException(status_code=404, detail="Course not found in cohort")
        
        return {"modules": modules}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get presenter cohort course modules error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch course modules")

@router.get("/presenter/cohorts/{cohort_id}/courses/{course_id}/modules/{module_id}/sessions")
async def get_presenter_cohort_module_sessions(
    cohort_id: int,
    course_id: int,
    module_id: int,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    """Get sessions for a specific module in a cohort course (presenter access)"""
    try:
        # Verify presenter has access to this cohort
        presenter_cohort = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == current_presenter.id,
            PresenterCohort.cohort_id == cohort_id
        ).first()
        
        if not presenter_cohort:
            raise HTTPException(status_code=403, detail="Access denied: Cohort not assigned to presenter")
        
        from cohort_specific_models import CohortSpecificCourse, CohortCourseModule, CohortCourseSession
        from database import Course, CohortCourse, Module, Session as DBSession
        
        sessions = []
        
        # Check if it's a cohort-specific course
        cohort_course = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.id == course_id,
            CohortSpecificCourse.cohort_id == cohort_id
        ).first()
        
        if cohort_course:
            # Verify module belongs to this course
            module = db.query(CohortCourseModule).filter(
                CohortCourseModule.id == module_id,
                CohortCourseModule.course_id == course_id
            ).first()
            
            if not module:
                raise HTTPException(status_code=404, detail="Module not found in course")
            
            # Get cohort-specific sessions
            cohort_sessions = db.query(CohortCourseSession).filter(
                CohortCourseSession.module_id == module_id
            ).order_by(CohortCourseSession.session_number).all()
            
            for session in cohort_sessions:
                sessions.append({
                    "id": session.id,
                    "title": session.title,
                    "description": session.description,
                    "session_number": session.session_number,
                    "scheduled_time": session.scheduled_time,
                    "duration_minutes": session.duration_minutes,
                    "zoom_link": session.zoom_link,
                    "recording_url": session.recording_url,
                    "syllabus_content": session.syllabus_content,
                    "is_cohort_specific": True
                })
        else:
            # Check if it's a global course assigned to cohort
            assignment = db.query(CohortCourse).filter(
                CohortCourse.cohort_id == cohort_id,
                CohortCourse.course_id == course_id
            ).first()
            
            if assignment:
                # Verify module belongs to this course
                module = db.query(Module).filter(
                    Module.id == module_id,
                    Module.course_id == course_id
                ).first()
                
                if not module:
                    raise HTTPException(status_code=404, detail="Module not found in course")
                
                # Get global course sessions
                global_sessions = db.query(DBSession).filter(
                    DBSession.module_id == module_id
                ).order_by(DBSession.session_number).all()
                
                for session in global_sessions:
                    sessions.append({
                        "id": session.id,
                        "title": session.title,
                        "description": session.description,
                        "session_number": session.session_number,
                        "scheduled_time": session.scheduled_time,
                        "duration_minutes": session.duration_minutes,
                        "zoom_link": session.zoom_link,
                        "recording_url": session.recording_url,
                        "syllabus_content": session.syllabus_content,
                        "is_cohort_specific": False
                    })
            else:
                raise HTTPException(status_code=404, detail="Course not found in cohort")
        
        return {"sessions": sessions}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get presenter cohort module sessions error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch module sessions")

@router.post("/presenter/cohorts/{cohort_id}/courses/{course_id}/modules/{module_id}/sessions")
async def create_presenter_cohort_session(
    cohort_id: int,
    course_id: int,
    module_id: int,
    session_data: dict,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    """Create a session for a cohort course module (presenter access)"""
    try:
        # Verify presenter has access to this cohort
        presenter_cohort = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == current_presenter.id,
            PresenterCohort.cohort_id == cohort_id
        ).first()
        
        if not presenter_cohort:
            raise HTTPException(status_code=403, detail="Access denied: Cohort not assigned to presenter")
        
        from cohort_specific_models import CohortSpecificCourse, CohortCourseModule, CohortCourseSession
        from database import Course, CohortCourse, Module, Session as DBSession
        
        # Check if it's a cohort-specific course
        cohort_course = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.id == course_id,
            CohortSpecificCourse.cohort_id == cohort_id
        ).first()
        
        if cohort_course:
            # Verify module belongs to this course
            module = db.query(CohortCourseModule).filter(
                CohortCourseModule.id == module_id,
                CohortCourseModule.course_id == course_id
            ).first()
            
            if not module:
                raise HTTPException(status_code=404, detail="Module not found in course")
            
            # Create cohort-specific session
            session = CohortCourseSession(
                module_id=module_id,
                session_number=session_data.get('session_number', 1),
                title=session_data.get('title', ''),
                description=session_data.get('description', ''),
                scheduled_time=session_data.get('scheduled_time'),
                duration_minutes=session_data.get('duration_minutes', 120),
                zoom_link=session_data.get('zoom_link', ''),
                syllabus_content=session_data.get('syllabus_content', '')
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            
            return {
                "id": session.id,
                "title": session.title,
                "description": session.description,
                "session_number": session.session_number,
                "scheduled_time": session.scheduled_time,
                "duration_minutes": session.duration_minutes,
                "zoom_link": session.zoom_link,
                "syllabus_content": session.syllabus_content,
                "is_cohort_specific": True
            }
        else:
            # For global courses, use admin session creation endpoint
            raise HTTPException(status_code=400, detail="Cannot create sessions for global courses through presenter interface")
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create presenter cohort session error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create session")

@router.delete("/presenter/cohorts/{cohort_id}/courses/{course_id}/modules/{module_id}/sessions/{session_id}")
async def delete_presenter_cohort_session(
    cohort_id: int,
    course_id: int,
    module_id: int,
    session_id: int,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    """Delete a session from a cohort course module (presenter access)"""
    try:
        # Verify presenter has access to this cohort
        presenter_cohort = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == current_presenter.id,
            PresenterCohort.cohort_id == cohort_id
        ).first()
        
        if not presenter_cohort:
            raise HTTPException(status_code=403, detail="Access denied: Cohort not assigned to presenter")
        
        from cohort_specific_models import CohortSpecificCourse, CohortCourseSession
        from database import Course, CohortCourse, Session as DBSession
        
        # Check if it's a cohort-specific course
        cohort_course = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.id == course_id,
            CohortSpecificCourse.cohort_id == cohort_id
        ).first()
        
        if cohort_course:
            # Delete cohort-specific session
            session = db.query(CohortCourseSession).filter(
                CohortCourseSession.id == session_id,
                CohortCourseSession.module_id == module_id
            ).first()
            
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            
            db.delete(session)
            db.commit()
            
            return {"message": "Session deleted successfully"}
        else:
            # For global courses, use admin session deletion endpoint
            raise HTTPException(status_code=400, detail="Cannot delete sessions for global courses through presenter interface")
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete presenter cohort session error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete session")

@router.put("/presenter/cohorts/{cohort_id}/courses/{course_id}/modules/{module_id}/sessions/{session_id}")
async def update_presenter_cohort_session(
    cohort_id: int,
    course_id: int,
    module_id: int,
    session_id: int,
    session_data: dict,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    """Update a session in a cohort course module (presenter access)"""
    try:
        # Verify presenter has access to this cohort
        presenter_cohort = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == current_presenter.id,
            PresenterCohort.cohort_id == cohort_id
        ).first()
        
        if not presenter_cohort:
            raise HTTPException(status_code=403, detail="Access denied: Cohort not assigned to presenter")
        
        from cohort_specific_models import CohortSpecificCourse, CohortCourseSession
        from database import Course, CohortCourse, Session as DBSession
        
        # Check if it's a cohort-specific course
        cohort_course = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.id == course_id,
            CohortSpecificCourse.cohort_id == cohort_id
        ).first()
        
        if cohort_course:
            # Update cohort-specific session
            session = db.query(CohortCourseSession).filter(
                CohortCourseSession.id == session_id,
                CohortCourseSession.module_id == module_id
            ).first()
            
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Update session fields
            session.session_number = session_data.get('session_number', session.session_number)
            session.title = session_data.get('title', session.title)
            session.description = session_data.get('description', session.description)
            session.scheduled_time = session_data.get('scheduled_time', session.scheduled_time)
            session.duration_minutes = session_data.get('duration_minutes', session.duration_minutes)
            session.zoom_link = session_data.get('zoom_link', session.zoom_link)
            session.syllabus_content = session_data.get('syllabus_content', session.syllabus_content)
            
            db.commit()
            db.refresh(session)
            
            return {
                "id": session.id,
                "title": session.title,
                "description": session.description,
                "session_number": session.session_number,
                "scheduled_time": session.scheduled_time,
                "duration_minutes": session.duration_minutes,
                "zoom_link": session.zoom_link,
                "syllabus_content": session.syllabus_content,
                "is_cohort_specific": True
            }
        else:
            # For global courses, use admin session update endpoint
            raise HTTPException(status_code=400, detail="Cannot update sessions for global courses through presenter interface")
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update presenter cohort session error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update session")

@router.get("/presenter/cohorts/{cohort_id}/courses/{course_id}/modules/{module_id}")
async def get_presenter_cohort_module(
    cohort_id: int,
    course_id: int,
    module_id: int,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    """Get details of a specific module in a cohort course (presenter access)"""
    try:
        # Verify presenter has access to this cohort
        presenter_cohort = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == current_presenter.id,
            PresenterCohort.cohort_id == cohort_id
        ).first()
        
        if not presenter_cohort:
            raise HTTPException(status_code=403, detail="Access denied: Cohort not assigned to presenter")
        
        from cohort_specific_models import CohortSpecificCourse, CohortCourseModule
        from database import Course, CohortCourse, Module
        
        # Check if it's a cohort-specific course
        cohort_course = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.id == course_id,
            CohortSpecificCourse.cohort_id == cohort_id
        ).first()
        
        if cohort_course:
            # Get cohort-specific module
            module = db.query(CohortCourseModule).filter(
                CohortCourseModule.id == module_id,
                CohortCourseModule.course_id == course_id
            ).first()
            
            if not module:
                raise HTTPException(status_code=404, detail="Module not found")
            
            return {
                "id": module.id,
                "title": module.title,
                "description": module.description,
                "week_number": module.week_number,
                "start_date": module.start_date,
                "end_date": module.end_date,
                "course_id": module.course_id,
                "is_cohort_specific": True
            }
        else:
            # Check if it's a global course assigned to cohort
            assignment = db.query(CohortCourse).filter(
                CohortCourse.cohort_id == cohort_id,
                CohortCourse.course_id == course_id
            ).first()
            
            if assignment:
                # Get global module
                module = db.query(Module).filter(
                    Module.id == module_id,
                    Module.course_id == course_id
                ).first()
                
                if not module:
                    raise HTTPException(status_code=404, detail="Module not found")
                
                return {
                    "id": module.id,
                    "title": module.title,
                    "description": module.description,
                    "week_number": module.week_number,
                    "start_date": module.start_date,
                    "end_date": module.end_date,
                    "course_id": module.course_id,
                    "is_cohort_specific": False
                }
            else:
                raise HTTPException(status_code=404, detail="Course not found in cohort")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get presenter cohort module error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch module details")


async def get_cohort_users(
    cohort_id: int,
    page: int = 1,
    limit: int = 50,
    search: Optional[str] = None,
    role: Optional[str] = None,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    """Get users in a specific cohort (only if presenter has access to this cohort)"""
    try:
        # Verify presenter has access to this cohort
        presenter_cohort = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == current_presenter.id,
            PresenterCohort.cohort_id == cohort_id
        ).first()
        
        if not presenter_cohort:
            raise HTTPException(status_code=403, detail="Access denied: Cohort not assigned to presenter")
        
        # Verify cohort exists
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Base query for users in the cohort
        query = db.query(User).join(UserCohort).filter(
            UserCohort.cohort_id == cohort_id,
            User.user_type.in_(['Student', 'Faculty'])
        )
        
        # Apply search filter
        if search:
            query = query.filter(
                or_(
                    User.username.contains(search),
                    User.email.contains(search),
                    User.college.contains(search)
                )
            )
        
        # Apply role filter
        if role:
            query = query.filter(User.user_type == role)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        users = query.offset((page - 1) * limit).limit(limit).all()
        
        # Format response
        user_list = []
        for user in users:
            user_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "college": user.college,
                "department": user.department,
                "year": user.year,
                "user_type": user.user_type,
                "active": True,
                "created_at": user.created_at
            }
            
            # Add faculty-specific fields if user is faculty
            if user.user_type == 'Faculty':
                user_data.update({
                    "experience": user.experience,
                    "designation": user.designation,
                    "specialization": user.specialization,
                    "employment_type": user.employment_type,
                    "joining_date": user.joining_date
                })
            
            user_list.append(user_data)
        
        return {
            "users": user_list,
            "total": total,
            "page": page,
            "limit": limit,
            "cohort": {
                "id": cohort.id,
                "name": cohort.name,
                "description": cohort.description
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get cohort users error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch cohort users")