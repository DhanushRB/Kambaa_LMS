"""
Mentor Endpoints for Admin and Mentor Operations
Handles mentor creation, assignment, authentication, and dashboard
"""

from fastapi import APIRouter, Depends, HTTPException, Request, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import logging
import os
import shutil
from pathlib import Path

from database import (
    get_db, Mentor, MentorCohort, MentorCourse, MentorSession, MentorLog,
    Admin, Cohort, Course, Session as SessionModel, Module, Resource,
    SessionContent, User, Enrollment, CohortCourse
)
from cohort_specific_models import CohortSpecificCourse, CohortCourseModule, CohortCourseSession

# Import Quiz from assignment_quiz_tables
try:
    from assignment_quiz_tables import Quiz
except ImportError:
    Quiz = None
from sqlalchemy import func
from auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_admin_or_presenter, get_current_mentor, ACCESS_TOKEN_EXPIRE_MINUTES
)
from schemas import ChangePasswordRequest

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic Models
class MentorLogin(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

class MentorCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None
    cohort_ids: List[int] = []
    course_ids: List[int] = []
    session_ids: List[int] = []

class MentorUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = Field(None, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    password: Optional[str] = Field(None, min_length=6)
    full_name: Optional[str] = None
    is_active: Optional[bool] = None

class MentorUpdateWithAssignments(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = Field(None, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    password: Optional[str] = Field(None, min_length=6)
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    cohort_ids: Optional[List[int]] = None
    course_ids: Optional[List[int]] = None
    session_ids: Optional[List[int]] = None

class MentorAssignment(BaseModel):
    mentor_id: int
    cohort_ids: List[int] = []
    course_ids: List[int] = []
    session_ids: List[int] = []

# Helper function for URL formatting
def format_meeting_url(url: str) -> str:
    """Ensure meeting URL has proper protocol for opening in browser"""
    if not url:
        return url
    
    url = url.strip()
    if not url:
        return url
    
    # If URL already has protocol, return as is
    if url.startswith(('http://', 'https://')):
        return url
    
    # Add https:// as default protocol
    return f"https://{url}"

# Helper function for logging
def log_mentor_action(mentor_id: int, mentor_username: str, action_type: str,
                      resource_type: str = None, resource_id: int = None,
                      details: str = None, db: Session = None):
    """Log mentor actions"""
    try:
        if db:
            log_entry = MentorLog(
                mentor_id=mentor_id,
                mentor_username=mentor_username,
                action_type=action_type,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details
            )
            db.add(log_entry)
            db.commit()
    except Exception as e:
        logger.error(f"Error logging mentor action: {str(e)}")

# ==================== MENTOR AUTHENTICATION ====================

@router.post("/mentor/login")
async def mentor_login(mentor_data: MentorLogin, request: Request, db: Session = Depends(get_db)):
    """Mentor login endpoint"""
    try:
        mentor = db.query(Mentor).filter(
            Mentor.username == mentor_data.username
        ).first()
        
        if not mentor or not verify_password(mentor_data.password, mentor.password_hash):
            log_mentor_action(
                mentor_id=mentor.id if mentor else 0,
                mentor_username=mentor_data.username,
                action_type="LOGIN_FAILED",
                details=f"Failed login attempt from IP: {request.client.host if request.client else 'Unknown'}",
                db=db
            )
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        if not mentor.is_active:
            raise HTTPException(status_code=403, detail="Account is inactive")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": mentor.username, "role": "Mentor"},
            expires_delta=access_token_expires
        )
        
        log_mentor_action(
            mentor_id=mentor.id,
            mentor_username=mentor.username,
            action_type="LOGIN",
            details=f"Successful login from IP: {request.client.host if request.client else 'Unknown'}",
            db=db
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "role": "Mentor",
            "username": mentor.username,
            "email": mentor.email,
            "full_name": mentor.full_name
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mentor login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")

@router.post("/mentor/logout")
async def mentor_logout(
    request: Request,
    current_mentor: Mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    """Mentor logout endpoint"""
    try:
        log_mentor_action(
            mentor_id=current_mentor.id,
            mentor_username=current_mentor.username,
            action_type="LOGOUT",
            details=f"Logged out from IP: {request.client.host if request.client else 'Unknown'}",
            db=db
        )
        return {"message": "Logged out successfully"}
    except Exception as e:
        logger.error(f"Mentor logout error: {str(e)}")
        raise HTTPException(status_code=500, detail="Logout failed")

@router.post("/mentor/change-password")
async def change_mentor_password(
    password_data: ChangePasswordRequest,
    current_mentor: Mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    """Mentor change password endpoint"""
    try:
        if not verify_password(password_data.current_password, current_mentor.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        
        current_mentor.password_hash = get_password_hash(password_data.new_password)
        db.commit()
        
        log_mentor_action(
            mentor_id=current_mentor.id,
            mentor_username=current_mentor.username,
            action_type="CHANGE_PASSWORD",
            resource_type="MENTOR_ACCOUNT",
            details="Password changed successfully",
            db=db
        )
        
        return {"message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Change mentor password error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to change password")

# ==================== ADMIN: MENTOR MANAGEMENT ====================

@router.post("/admin/mentors")
async def create_mentor(
    mentor_data: MentorCreate,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Admin creates a new mentor with assignments"""
    try:
        # Check if username or email already exists
        existing = db.query(Mentor).filter(
            or_(Mentor.username == mentor_data.username, Mentor.email == mentor_data.email)
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Username or email already exists")
        
        # Create mentor
        mentor = Mentor(
            username=mentor_data.username,
            email=mentor_data.email,
            password_hash=get_password_hash(mentor_data.password),
            full_name=mentor_data.full_name,
            is_active=True
        )
        db.add(mentor)
        db.flush()
        
        # Assign cohorts
        for cohort_id in mentor_data.cohort_ids:
            cohort_assignment = MentorCohort(
                mentor_id=mentor.id,
                cohort_id=cohort_id,
                assigned_by=current_admin.id
            )
            db.add(cohort_assignment)
        
        # Assign courses
        for course_id in mentor_data.course_ids:
            course_assignment = MentorCourse(
                mentor_id=mentor.id,
                course_id=course_id,
                assigned_by=current_admin.id
            )
            db.add(course_assignment)
        
        # Assign sessions
        for session_id in mentor_data.session_ids:
            # Get session to get course and cohort info
            session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            if session:
                session_assignment = MentorSession(
                    mentor_id=mentor.id,
                    session_id=session_id,
                    course_id=session.module.course_id if session.module else None,
                    assigned_by=current_admin.id
                )
                db.add(session_assignment)
        
        db.commit()
        db.refresh(mentor)
        
        return {
            "message": "Mentor created successfully",
            "mentor": {
                "id": mentor.id,
                "username": mentor.username,
                "email": mentor.email,
                "full_name": mentor.full_name,
                "is_active": mentor.is_active,
                "created_at": mentor.created_at
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create mentor error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create mentor: {str(e)}")

@router.get("/admin/mentors")
async def get_mentors(
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Admin gets list of all mentors"""
    try:
        query = db.query(Mentor)
        
        if search:
            query = query.filter(
                or_(
                    Mentor.username.ilike(f"%{search}%"),
                    Mentor.email.ilike(f"%{search}%"),
                    Mentor.full_name.ilike(f"%{search}%")
                )
            )
        
        total = query.count()
        mentors = query.offset((page - 1) * limit).limit(limit).all()
        
        mentor_list = []
        for mentor in mentors:
            # Get assignments
            cohorts = db.query(MentorCohort).filter(MentorCohort.mentor_id == mentor.id).count()
            courses = db.query(MentorCourse).filter(MentorCourse.mentor_id == mentor.id).count()
            sessions = db.query(MentorSession).filter(MentorSession.mentor_id == mentor.id).count()
            
            mentor_list.append({
                "id": mentor.id,
                "username": mentor.username,
                "email": mentor.email,
                "full_name": mentor.full_name,
                "is_active": mentor.is_active,
                "created_at": mentor.created_at,
                "assigned_cohorts": cohorts,
                "assigned_courses": courses,
                "assigned_sessions": sessions
            })
        
        return {
            "mentors": mentor_list,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
    except Exception as e:
        logger.error(f"Get mentors error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch mentors")

@router.get("/admin/mentors/{mentor_id}")
async def get_mentor_details(
    mentor_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Admin gets detailed mentor information with assignments"""
    try:
        mentor = db.query(Mentor).filter(Mentor.id == mentor_id).first()
        if not mentor:
            raise HTTPException(status_code=404, detail="Mentor not found")
        
        # Get assigned cohorts
        cohorts = db.query(Cohort).join(MentorCohort).filter(
            MentorCohort.mentor_id == mentor_id
        ).all()
        
        # Get assigned courses
        courses = db.query(Course).join(MentorCourse).filter(
            MentorCourse.mentor_id == mentor_id
        ).all()
        
        # Get assigned sessions
        sessions = db.query(SessionModel).join(MentorSession).filter(
            MentorSession.mentor_id == mentor_id
        ).all()
        
        return {
            "mentor": {
                "id": mentor.id,
                "username": mentor.username,
                "email": mentor.email,
                "full_name": mentor.full_name,
                "is_active": mentor.is_active,
                "created_at": mentor.created_at
            },
            "assignments": {
                "cohorts": [{"id": c.id, "name": c.name} for c in cohorts],
                "courses": [{"id": c.id, "title": c.title} for c in courses],
                "sessions": [{
                    "id": s.id,
                    "title": s.title,
                    "module_id": s.module_id,
                    "scheduled_time": s.scheduled_time
                } for s in sessions]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get mentor details error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch mentor details")

@router.get("/admin/mentors/{mentor_id}/assignments")
async def get_mentor_assignments(
    mentor_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get mentor assignments (cohorts, courses, sessions) for editing"""
    try:
        mentor = db.query(Mentor).filter(Mentor.id == mentor_id).first()
        if not mentor:
            raise HTTPException(status_code=404, detail="Mentor not found")
        
        # Get assigned cohort IDs
        cohort_ids = [mc.cohort_id for mc in db.query(MentorCohort).filter(
            MentorCohort.mentor_id == mentor_id
        ).all()]
        
        # Get assigned course IDs
        course_ids = [mc.course_id for mc in db.query(MentorCourse).filter(
            MentorCourse.mentor_id == mentor_id
        ).all()]
        
        # Get assigned session IDs
        session_ids = [ms.session_id for ms in db.query(MentorSession).filter(
            MentorSession.mentor_id == mentor_id
        ).all()]
        
        return {
            "cohort_ids": cohort_ids,
            "course_ids": course_ids,
            "session_ids": session_ids
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get mentor assignments error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch mentor assignments")

@router.put("/admin/mentors/{mentor_id}")
async def update_mentor(
    mentor_id: int,
    mentor_data: MentorUpdateWithAssignments,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Admin updates mentor information and assignments"""
    try:
        mentor = db.query(Mentor).filter(Mentor.id == mentor_id).first()
        if not mentor:
            raise HTTPException(status_code=404, detail="Mentor not found")
        
        # Update basic fields
        if mentor_data.username:
            # Check uniqueness
            existing = db.query(Mentor).filter(
                Mentor.username == mentor_data.username,
                Mentor.id != mentor_id
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Username already exists")
            mentor.username = mentor_data.username
        
        if mentor_data.email:
            # Check uniqueness
            existing = db.query(Mentor).filter(
                Mentor.email == mentor_data.email,
                Mentor.id != mentor_id
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Email already exists")
            mentor.email = mentor_data.email
        
        if mentor_data.password:
            mentor.password_hash = get_password_hash(mentor_data.password)
        
        if mentor_data.full_name is not None:
            mentor.full_name = mentor_data.full_name
        
        if mentor_data.is_active is not None:
            mentor.is_active = mentor_data.is_active
        
        # Always update assignments if any assignment data is provided
        if (mentor_data.cohort_ids is not None or 
            mentor_data.course_ids is not None or 
            mentor_data.session_ids is not None):
            
            # Clear existing assignments
            db.query(MentorCohort).filter(MentorCohort.mentor_id == mentor_id).delete()
            db.query(MentorCourse).filter(MentorCourse.mentor_id == mentor_id).delete()
            db.query(MentorSession).filter(MentorSession.mentor_id == mentor_id).delete()
            
            # Add new cohort assignments
            if mentor_data.cohort_ids:
                for cohort_id in mentor_data.cohort_ids:
                    cohort_assignment = MentorCohort(
                        mentor_id=mentor_id,
                        cohort_id=cohort_id,
                        assigned_by=current_admin.id
                    )
                    db.add(cohort_assignment)
            
            # Add new course assignments
            if mentor_data.course_ids:
                for course_id in mentor_data.course_ids:
                    course_assignment = MentorCourse(
                        mentor_id=mentor_id,
                        course_id=course_id,
                        assigned_by=current_admin.id
                    )
                    db.add(course_assignment)
            
            # Add new session assignments
            if mentor_data.session_ids:
                for session_id in mentor_data.session_ids:
                    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
                    if session:
                        session_assignment = MentorSession(
                            mentor_id=mentor_id,
                            session_id=session_id,
                            course_id=session.module.course_id if session.module else None,
                            assigned_by=current_admin.id
                        )
                        db.add(session_assignment)
        
        db.commit()
        db.refresh(mentor)
        
        return {
            "message": "Mentor updated successfully",
            "mentor": {
                "id": mentor.id,
                "username": mentor.username,
                "email": mentor.email,
                "full_name": mentor.full_name,
                "is_active": mentor.is_active
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update mentor error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update mentor")

@router.delete("/admin/mentors/{mentor_id}")
async def delete_mentor(
    mentor_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Admin deletes a mentor (cascades to assignments)"""
    try:
        mentor = db.query(Mentor).filter(Mentor.id == mentor_id).first()
        if not mentor:
            raise HTTPException(status_code=404, detail="Mentor not found")
        
        # Manually delete related records that might not cascade properly
        db.query(MentorLog).filter(MentorLog.mentor_id == mentor_id).delete()
        db.query(MentorCohort).filter(MentorCohort.mentor_id == mentor_id).delete()
        db.query(MentorCourse).filter(MentorCourse.mentor_id == mentor_id).delete()
        db.query(MentorSession).filter(MentorSession.mentor_id == mentor_id).delete()
        
        # Delete the mentor
        db.delete(mentor)
        db.commit()
        
        return {"message": "Mentor deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete mentor error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete mentor")

@router.post("/admin/mentors/{mentor_id}/assign")
async def assign_mentor_resources(
    mentor_id: int,
    assignment: MentorAssignment,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Admin assigns cohorts, courses, and sessions to mentor"""
    try:
        mentor = db.query(Mentor).filter(Mentor.id == mentor_id).first()
        if not mentor:
            raise HTTPException(status_code=404, detail="Mentor not found")
        
        # Clear existing assignments
        db.query(MentorCohort).filter(MentorCohort.mentor_id == mentor_id).delete()
        db.query(MentorCourse).filter(MentorCourse.mentor_id == mentor_id).delete()
        db.query(MentorSession).filter(MentorSession.mentor_id == mentor_id).delete()
        
        # Assign cohorts
        for cohort_id in assignment.cohort_ids:
            cohort_assignment = MentorCohort(
                mentor_id=mentor_id,
                cohort_id=cohort_id,
                assigned_by=current_admin.id
            )
            db.add(cohort_assignment)
        
        # Assign courses
        for course_id in assignment.course_ids:
            course_assignment = MentorCourse(
                mentor_id=mentor_id,
                course_id=course_id,
                assigned_by=current_admin.id
            )
            db.add(course_assignment)
        
        # Assign sessions
        for session_id in assignment.session_ids:
            session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            if session:
                session_assignment = MentorSession(
                    mentor_id=mentor_id,
                    session_id=session_id,
                    course_id=session.module.course_id if session.module else None,
                    assigned_by=current_admin.id
                )
                db.add(session_assignment)
        
        db.commit()
        
        # Send notification to mentor
        try:
            from course_assignment_notifications import notify_mentor_assignment
            notify_mentor_assignment(db, mentor_id, assignment.cohort_ids, assignment.course_ids, current_admin.username)
        except Exception as e:
            print(f"Notification error: {e}")
        
        return {
            "message": "Assignments updated successfully",
            "assigned": {
                "cohorts": len(assignment.cohort_ids),
                "courses": len(assignment.course_ids),
                "sessions": len(assignment.session_ids)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Assign mentor resources error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to assign resources")

# ==================== MENTOR DASHBOARD ====================

@router.get("/mentor/dashboard")
async def get_mentor_dashboard(
    current_mentor: Mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    """Mentor dashboard overview with upcoming sessions"""
    try:
        from database import Session as SessionModel
        
        # Get assigned sessions count
        total_sessions = db.query(MentorSession).filter(
            MentorSession.mentor_id == current_mentor.id
        ).count()
        
        # Get assigned courses count
        total_courses = db.query(MentorCourse).filter(
            MentorCourse.mentor_id == current_mentor.id
        ).count()
        
        # Get assigned cohorts count
        total_cohorts = db.query(MentorCohort).filter(
            MentorCohort.mentor_id == current_mentor.id
        ).count()
        
        # Get students from assigned cohorts
        cohort_ids = [c.cohort_id for c in db.query(MentorCohort).filter(
            MentorCohort.mentor_id == current_mentor.id
        ).all()]
        
        total_students = 0
        if cohort_ids:
            total_students = db.query(User).filter(
                User.cohort_id.in_(cohort_ids)
            ).count()
        
        # Get upcoming sessions for mentor
        current_time = datetime.now()
        upcoming_sessions = db.query(SessionModel).join(MentorSession).join(Module).join(Course).filter(
            MentorSession.mentor_id == current_mentor.id,
            SessionModel.scheduled_time.isnot(None),
            SessionModel.scheduled_time > current_time
        ).order_by(SessionModel.scheduled_time).limit(10).all()
        
        sessions_data = []
        for session in upcoming_sessions:
            module = db.query(Module).filter(Module.id == session.module_id).first()
            course = db.query(Course).filter(Course.id == module.course_id).first() if module else None
            
            sessions_data.append({
                "id": session.id,
                "title": session.title,
                "course_title": course.title if course else "Unknown Course",
                "module_title": module.title if module else "Unknown Module",
                "scheduled_date": session.scheduled_time.strftime("%Y-%m-%d") if session.scheduled_time else None,
                "scheduled_time": session.scheduled_time.strftime("%H:%M") if session.scheduled_time else None,
                "scheduled_datetime": session.scheduled_time,
                "duration_minutes": session.duration_minutes,
                "zoom_link": session.zoom_link,
                "session_number": session.session_number,
                "week_number": module.week_number if module else None
            })
        
        return {
            "mentor": {
                "id": current_mentor.id,
                "username": current_mentor.username,
                "email": current_mentor.email,
                "full_name": current_mentor.full_name
            },
            "stats": {
                "total_cohorts": total_cohorts,
                "total_courses": total_courses,
                "total_sessions": total_sessions,
                "total_students": total_students
            },
            "upcoming_sessions": sessions_data,
            "total_upcoming": len(sessions_data)
        }
    except Exception as e:
        logger.error(f"Get mentor dashboard error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard")

@router.get("/mentor/sessions")
async def get_mentor_sessions(
    current_mentor: Mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    """Get only sessions specifically assigned to mentor by admin"""
    try:
        # Only get sessions that are explicitly assigned to this mentor
        sessions = db.query(SessionModel).join(MentorSession).filter(
            MentorSession.mentor_id == current_mentor.id
        ).all()
        
        session_list = []
        for session in sessions:
            module = session.module
            course = module.course if module else None
            
            # Additional check: ensure mentor has access to the course
            if course:
                course_assignment = db.query(MentorCourse).filter(
                    and_(
                        MentorCourse.mentor_id == current_mentor.id,
                        MentorCourse.course_id == course.id
                    )
                ).first()
                
                # Only include session if mentor has course access
                if course_assignment:
                    session_list.append({
                        "id": session.id,
                        "title": session.title,
                        "description": session.description,
                        "session_number": session.session_number,
                        "scheduled_time": session.scheduled_time,
                        "duration_minutes": session.duration_minutes,
                        "zoom_link": session.zoom_link,
                        "module": {
                            "id": module.id,
                            "title": module.title
                        } if module else None,
                        "course": {
                            "id": course.id,
                            "title": course.title
                        } if course else None
                    })
        
        return {"sessions": session_list}
    except Exception as e:
        logger.error(f"Get mentor sessions error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch sessions")

@router.get("/mentor/session/{session_id}/content")
async def get_session_content_for_mentor(
    session_id: int,
    current_mentor: Mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    """Get content for a specific session (mentor view)"""
    try:
        # Verify mentor has access to this session
        assignment = db.query(MentorSession).filter(
            and_(
                MentorSession.mentor_id == current_mentor.id,
                MentorSession.session_id == session_id
            )
        ).first()
        
        if not assignment:
            raise HTTPException(status_code=403, detail="You don't have access to this session")
        
        # Get resources
        resources = db.query(Resource).filter(Resource.session_id == session_id).all()
        
        # Get session content (including meeting links)
        content = db.query(SessionContent).filter(SessionContent.session_id == session_id).all()
        
        # Get quizzes (only if Quiz model is available)
        quizzes = []
        if Quiz:
            quizzes = db.query(Quiz).filter(Quiz.session_id == session_id).all()
        
        # Combine resources and session content for unified view
        all_resources = []
        
        # Add regular resources
        for r in resources:
            all_resources.append({
                "id": r.id,
                "title": r.title,
                "resource_type": r.resource_type,
                "content_type": "RESOURCE",
                "file_size": r.file_size,
                "description": r.description,
                "file_path": r.file_path,
                "meeting_url": None,
                "uploaded_at": r.uploaded_at,
                "created_at": r.created_at
            })
        
        # Add session content (including meeting links)
        for c in content:
            all_resources.append({
                "id": f"content_{c.id}",
                "title": c.title,
                "resource_type": c.content_type,
                "content_type": c.content_type,
                "file_size": c.file_size,
                "description": c.description,
                "file_path": c.file_path,
                "meeting_url": format_meeting_url(c.meeting_url) if c.meeting_url else None,
                "uploaded_at": None,
                "created_at": c.created_at
            })
        
        return {
            "resources": all_resources,
            "quizzes": [{
                "id": q.id,
                "title": q.title,
                "description": q.description,
                "total_marks": q.total_marks,
                "time_limit_minutes": q.time_limit_minutes,
                "created_at": q.created_at
            } for q in quizzes]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get session content error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch session content")

@router.get("/mentor/session/{session_id}/resources")
async def get_session_resources_for_mentor(
    session_id: int,
    current_mentor: Mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    """Get resources for a specific session (mentor view)"""
    try:
        # Verify mentor has access to this session
        assignment = db.query(MentorSession).filter(
            and_(
                MentorSession.mentor_id == current_mentor.id,
                MentorSession.session_id == session_id
            )
        ).first()
        
        if not assignment:
            raise HTTPException(status_code=403, detail="You don't have access to this session")
        
        # Get resources from Resource table
        resources = db.query(Resource).filter(Resource.session_id == session_id).all()
        
        # Get session content (including meeting links)
        session_content = db.query(SessionContent).filter(SessionContent.session_id == session_id).all()
        
        # Combine both types of resources
        all_resources = []
        
        # Add regular resources
        for r in resources:
            all_resources.append({
                "id": r.id,
                "title": r.title,
                "resource_type": r.resource_type,
                "content_type": "RESOURCE",
                "file_size": r.file_size,
                "description": r.description,
                "file_path": r.file_path,
                "meeting_url": None,
                "uploaded_at": r.uploaded_at,
                "created_at": r.created_at
            })
        
        # Add session content (including meeting links)
        for c in session_content:
            all_resources.append({
                "id": f"content_{c.id}",
                "title": c.title,
                "resource_type": c.content_type,
                "content_type": c.content_type,
                "file_size": c.file_size,
                "description": c.description,
                "file_path": c.file_path,
                "meeting_url": format_meeting_url(c.meeting_url) if c.meeting_url else None,
                "uploaded_at": None,
                "created_at": c.created_at
            })
        
        return {"resources": all_resources}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get session resources error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch session resources")

@router.get("/mentor/session/{session_id}/quizzes")
async def get_session_quizzes_for_mentor(
    session_id: int,
    current_mentor: Mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    """Get quizzes for a specific session (mentor view)"""
    try:
        # Verify mentor has access to this session
        assignment = db.query(MentorSession).filter(
            and_(
                MentorSession.mentor_id == current_mentor.id,
                MentorSession.session_id == session_id
            )
        ).first()
        
        if not assignment:
            raise HTTPException(status_code=403, detail="You don't have access to this session")
        
        # Get quizzes (only if Quiz model is available)
        quizzes = []
        if Quiz:
            quizzes = db.query(Quiz).filter(Quiz.session_id == session_id).all()
        
        return [{
            "id": q.id,
            "title": q.title,
            "description": q.description,
            "total_marks": q.total_marks,
            "time_limit_minutes": q.time_limit_minutes,
            "is_active": q.is_active,
            "created_at": q.created_at
        } for q in quizzes]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get session quizzes error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch session quizzes")

@router.get("/mentor/courses")
async def get_mentor_courses(
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    is_active: Optional[str] = None,
    current_mentor: Mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    """Get only courses assigned to mentor by admin"""
    try:
        # Only get courses that are explicitly assigned to this mentor
        query = db.query(Course).join(MentorCourse).filter(
            MentorCourse.mentor_id == current_mentor.id
        )
        
        # Apply filters
        if search:
            query = query.filter(
                or_(
                    Course.title.ilike(f"%{search}%"),
                    Course.description.ilike(f"%{search}%")
                )
            )
        
        # Note: Removed is_active filter since Course model doesn't have this attribute
        
        courses = query.all()
        
        course_list = []
        for course in courses:
            # Get course statistics
            modules_count = db.query(Module).filter(Module.course_id == course.id).count()
            enrolled_students = db.query(Enrollment).filter(Enrollment.course_id == course.id).count()
            
            # Calculate duration from modules
            max_week = db.query(func.max(Module.week_number)).filter(Module.course_id == course.id).scalar()
            duration_weeks = max_week if max_week else 0
            
            course_list.append({
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "duration_weeks": duration_weeks,
                "modules_count": modules_count,
                "enrolled_students": enrolled_students,
                "is_active": True,  # Default to True since Course model doesn't have is_active
                "created_at": course.created_at
            })
        
        return {"courses": course_list}
    except Exception as e:
        logger.error(f"Get mentor courses error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch courses")

@router.get("/mentor/courses/{course_id}/modules")
async def get_mentor_course_modules(
    course_id: int,
    current_mentor: Mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    """Get only modules for assigned course"""
    try:
        # Verify mentor has access to this course
        assignment = db.query(MentorCourse).filter(
            and_(
                MentorCourse.mentor_id == current_mentor.id,
                MentorCourse.course_id == course_id
            )
        ).first()
        
        if not assignment:
            raise HTTPException(status_code=403, detail="You don't have access to this course")
        
        # Determine if it's a global or cohort course
        modules = db.query(Module).filter(Module.course_id == course_id).order_by(Module.week_number).all()
        is_cohort = False
        
        if not modules:
            modules = db.query(CohortCourseModule).filter(CohortCourseModule.course_id == course_id).order_by(CohortCourseModule.week_number).all()
            is_cohort = True
        
        module_list = []
        for module in modules:
            # Only count sessions that are assigned to this mentor
            if is_cohort:
                assigned_sessions = db.query(CohortCourseSession).join(MentorSession, MentorSession.session_id == CohortCourseSession.id).filter(
                    and_(
                        CohortCourseSession.module_id == module.id,
                        MentorSession.mentor_id == current_mentor.id
                    )
                ).all()
            else:
                assigned_sessions = db.query(SessionModel).join(MentorSession, MentorSession.session_id == SessionModel.id).filter(
                    and_(
                        SessionModel.module_id == module.id,
                        MentorSession.mentor_id == current_mentor.id
                    )
                ).all()
            
            # Get statistics only for assigned sessions
            total_resources = 0
            if is_cohort:
                from cohort_specific_models import CohortSessionContent, CohortCourseResource
                for s in assigned_sessions:
                    total_resources += db.query(CohortCourseResource).filter(CohortCourseResource.session_id == s.id).count()
                    total_resources += db.query(CohortSessionContent).filter(CohortSessionContent.session_id == s.id).count()
            else:
                for s in assigned_sessions:
                    total_resources += db.query(Resource).filter(Resource.session_id == s.id).count()
                    total_resources += db.query(SessionContent).filter(SessionContent.session_id == s.id).count()
            
            total_quizzes = sum([
                db.query(Quiz).filter(Quiz.session_id == s.id).count() if Quiz else 0
                for s in assigned_sessions
            ])
            
            # Only include module if mentor has assigned sessions in it
            if assigned_sessions:
                module_list.append({
                    "id": module.id,
                    "week_number": module.week_number,
                    "title": module.title,
                    "description": module.description,
                    "sessions_count": len(assigned_sessions),
                    "resources_count": total_resources,
                    "quizzes_count": total_quizzes,
                    "is_cohort_specific": is_cohort,
                    "created_at": module.created_at
                })
        
        return {"modules": module_list}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get mentor course modules error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch course modules")

@router.get("/mentor/modules/{module_id}/sessions")
async def get_mentor_module_sessions(
    module_id: int,
    current_mentor: Mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    """Get only sessions assigned to mentor in this module"""
    try:
        # Try to find if it's a regular module first
        module = db.query(Module).filter(Module.id == module_id).first()
        is_cohort = False
        
        if not module:
            # Check if it's a cohort module
            module = db.query(CohortCourseModule).filter(CohortCourseModule.id == module_id).first()
            if not module:
                raise HTTPException(status_code=404, detail="Module not found")
            is_cohort = True
        
        # Verify mentor has access to this course
        course_assignment = db.query(MentorCourse).filter(
            and_(
                MentorCourse.mentor_id == current_mentor.id,
                MentorCourse.course_id == module.course_id
            )
        ).first()
        
        if not course_assignment:
            # If not direct course assignment, check if mentor is assigned to the cohort
            if is_cohort:
                cohort_assignment = db.query(MentorCohort).filter(
                    and_(
                        MentorCohort.mentor_id == current_mentor.id,
                        MentorCohort.cohort_id == module.course.cohort_id if hasattr(module, 'course') else None
                    )
                ).first()
                if not cohort_assignment:
                    raise HTTPException(status_code=403, detail="You don't have access to this module")
            else:
                raise HTTPException(status_code=403, detail="You don't have access to this module")
        
        # Only get sessions that are specifically assigned to this mentor
        if is_cohort:
            sessions = db.query(CohortCourseSession).join(MentorSession, MentorSession.session_id == CohortCourseSession.id).filter(
                and_(
                    CohortCourseSession.module_id == module_id,
                    MentorSession.mentor_id == current_mentor.id
                )
            ).order_by(CohortCourseSession.session_number).all()
        else:
            sessions = db.query(SessionModel).join(MentorSession, MentorSession.session_id == SessionModel.id).filter(
                and_(
                    SessionModel.module_id == module_id,
                    MentorSession.mentor_id == current_mentor.id
                )
            ).order_by(SessionModel.session_number).all()
        
        session_list = []
        for session in sessions:
            # Get session statistics
            if is_cohort:
                from cohort_specific_models import CohortSessionContent, CohortCourseResource
                resources_count = db.query(CohortCourseResource).filter(CohortCourseResource.session_id == session.id).count()
                session_content_count = db.query(CohortSessionContent).filter(CohortSessionContent.session_id == session.id).count()
            else:
                resources_count = db.query(Resource).filter(Resource.session_id == session.id).count()
                session_content_count = db.query(SessionContent).filter(SessionContent.session_id == session.id).count()
            
            total_resources_count = resources_count + session_content_count
            
            quizzes_count = db.query(Quiz).filter(Quiz.session_id == session.id).count() if Quiz else 0
            
            session_list.append({
                "id": session.id,
                "session_number": session.session_number,
                "title": session.title,
                "description": session.description,
                "scheduled_time": session.scheduled_time,
                "duration_minutes": session.duration_minutes,
                "zoom_link": session.zoom_link,
                "recording_url": session.recording_url,
                "resources_count": total_resources_count,
                "quizzes_count": quizzes_count,
                "is_cohort_specific": is_cohort,
                "created_at": session.created_at
            })
        
        return session_list
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get mentor module sessions error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch module sessions")

@router.get("/mentor/cohorts")
async def get_mentor_cohorts(
    current_mentor: Mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    """Get only cohorts specifically assigned to mentor by admin"""
    try:
        # Only get cohorts that are explicitly assigned to this mentor
        cohorts = db.query(Cohort).join(MentorCohort).filter(
            MentorCohort.mentor_id == current_mentor.id
        ).all()
        
        cohort_list = []
        for cohort in cohorts:
            # Get cohort statistics
            student_count = db.query(User).filter(
                User.cohort_id == cohort.id,
                User.role == "Student"
            ).count()
            
            # Only count courses that are also assigned to this mentor
            assigned_course_ids = [mc.course_id for mc in db.query(MentorCourse).filter(
                MentorCourse.mentor_id == current_mentor.id
            ).all()]
            
            course_count = db.query(CohortCourse).filter(
                and_(
                    CohortCourse.cohort_id == cohort.id,
                    CohortCourse.course_id.in_(assigned_course_ids)
                )
            ).count() if assigned_course_ids else 0
            
            cohort_list.append({
                "id": cohort.id,
                "name": cohort.name,
                "description": cohort.description,
                "instructor_name": cohort.instructor_name,
                "start_date": cohort.start_date,
                "end_date": cohort.end_date,
                "student_count": student_count,
                "course_count": course_count,
                "created_at": cohort.created_at
            })
        
        return {"cohorts": cohort_list}
    except Exception as e:
        logger.error(f"Get mentor cohorts error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch cohorts")

@router.get("/mentor/students")
async def get_mentor_students(
    current_mentor: Mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    """Get only students from cohorts assigned to mentor by admin"""
    try:
        # Get only cohort IDs that are explicitly assigned to this mentor
        cohort_ids = [c.cohort_id for c in db.query(MentorCohort).filter(
            MentorCohort.mentor_id == current_mentor.id
        ).all()]
        
        if not cohort_ids:
            return {"students": []}
        
        # Get students only from assigned cohorts
        students = db.query(User).filter(
            User.cohort_id.in_(cohort_ids),
            User.role == "Student"
        ).all()
        
        student_list = []
        for student in students:
            # Get cohort info
            cohort = db.query(Cohort).filter(Cohort.id == student.cohort_id).first()
            
            # Only count enrollments in courses assigned to this mentor
            assigned_course_ids = [mc.course_id for mc in db.query(MentorCourse).filter(
                MentorCourse.mentor_id == current_mentor.id
            ).all()]
            
            enrollments = db.query(Enrollment).filter(
                and_(
                    Enrollment.student_id == student.id,
                    Enrollment.course_id.in_(assigned_course_ids)
                )
            ).count() if assigned_course_ids else 0
            
            student_list.append({
                "id": student.id,
                "username": student.username,
                "email": student.email,
                "college": student.college,
                "department": student.department,
                "year": student.year,
                "cohort": cohort.name if cohort else None,
                "enrollments": enrollments
            })
        
        return {"students": student_list}
    except Exception as e:
        logger.error(f"Get mentor students error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch students")

# ==================== MENTOR RESOURCE MANAGEMENT ====================

@router.post("/mentor/upload/resource")
async def upload_resource_for_mentor(
    session_id: int,
    title: str,
    description: str = "",
    resource_type: str = "FILE",
    file: UploadFile = File(...),
    current_mentor: Mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    """Mentor uploads a resource to an assigned session"""
    try:
        # Verify mentor has access to this session
        assignment = db.query(MentorSession).filter(
            and_(
                MentorSession.mentor_id == current_mentor.id,
                MentorSession.session_id == session_id
            )
        ).first()
        
        if not assignment:
            raise HTTPException(status_code=403, detail="You don't have access to this session")
        
        # Create uploads directory if it doesn't exist
        upload_dir = Path("uploads/resources")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_extension = Path(file.filename).suffix
        unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        file_path = upload_dir / unique_filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Create resource record
        resource = Resource(
            session_id=session_id,
            title=title,
            description=description,
            resource_type=resource_type,
            file_path=str(file_path),
            file_size=file_path.stat().st_size,
            uploaded_by=current_mentor.id
        )
        db.add(resource)
        db.commit()
        db.refresh(resource)
        
        # Log the action
        log_mentor_action(
            mentor_id=current_mentor.id,
            mentor_username=current_mentor.username,
            action_type="UPLOAD_RESOURCE",
            resource_type="RESOURCE",
            resource_id=resource.id,
            details=f"Uploaded resource '{title}' to session {session_id}",
            db=db
        )
        
        return {
            "message": "Resource uploaded successfully",
            "resource": {
                "id": resource.id,
                "title": resource.title,
                "description": resource.description,
                "resource_type": resource.resource_type,
                "file_size": resource.file_size,
                "created_at": resource.created_at
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Upload resource error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload resource")

@router.post("/mentor/session-content")
async def create_session_content_for_mentor(
    content_data: dict,
    current_mentor: Mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    """Mentor creates session content (meeting links, materials, etc.)"""
    try:
        session_id = content_data.get('session_id')
        if not session_id:
            raise HTTPException(status_code=400, detail="Session ID is required")
        
        # Verify mentor has access to this session
        assignment = db.query(MentorSession).filter(
            and_(
                MentorSession.mentor_id == current_mentor.id,
                MentorSession.session_id == session_id
            )
        ).first()
        
        if not assignment:
            raise HTTPException(status_code=403, detail="You don't have access to this session")
        
        # Create session content record
        session_content = SessionContent(
            session_id=session_id,
            title=content_data.get('title', ''),
            description=content_data.get('description', ''),
            content_type=content_data.get('content_type', 'MATERIAL'),
            meeting_url=content_data.get('meeting_url'),
            scheduled_time=content_data.get('scheduled_time'),
            uploaded_by=current_mentor.id
        )
        db.add(session_content)
        db.commit()
        db.refresh(session_content)
        
        # Log the action
        log_mentor_action(
            mentor_id=current_mentor.id,
            mentor_username=current_mentor.username,
            action_type="CREATE_CONTENT",
            resource_type="SESSION_CONTENT",
            resource_id=session_content.id,
            details=f"Created {content_data.get('content_type', 'content')} '{content_data.get('title', '')}' for session {session_id}",
            db=db
        )
        
        return {
            "message": "Session content created successfully",
            "content": {
                "id": session_content.id,
                "title": session_content.title,
                "description": session_content.description,
                "content_type": session_content.content_type,
                "meeting_url": session_content.meeting_url,
                "created_at": session_content.created_at
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create session content error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create session content")

