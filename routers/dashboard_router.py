from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db, User, Admin, Course, Module, SessionModel, Enrollment, Cohort, PresenterCohort, CohortCourse
from auth import get_current_admin_or_presenter, get_current_admin_presenter_mentor_or_manager, get_current_presenter
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dashboard"])

@router.get("/admin/dashboard")
async def get_admin_dashboard(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Admin dashboard with analytics and upcoming sessions"""
    try:
        # Get basic analytics
        total_students = db.query(User).filter(User.role == "Student").count()
        total_courses = db.query(Course).count()
        total_sessions = db.query(SessionModel).count()
        total_enrollments = db.query(Enrollment).count()
        
        # Get upcoming sessions
        current_time = datetime.now()
        upcoming_sessions = db.query(SessionModel).join(Module, SessionModel.module_id == Module.id).join(Course, Module.course_id == Course.id).filter(
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
            "analytics": {
                "total_students": total_students,
                "total_courses": total_courses,
                "total_sessions": total_sessions,
                "total_enrollments": total_enrollments
            },
            "upcoming_sessions": sessions_data,
            "total_upcoming": len(sessions_data)
        }
    except Exception as e:
        logger.error(f"Admin dashboard error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard data")

@router.get("/presenter/dashboard")
async def get_presenter_dashboard(
    current_presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    """Presenter dashboard with filtered data based on assigned cohorts and upcoming sessions"""
    try:
        # Get cohorts assigned to this presenter
        presenter_cohorts = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == current_presenter.id
        ).all()
        
        assigned_cohort_ids = [pc.cohort_id for pc in presenter_cohorts]
        
        # Get upcoming sessions for presenter's cohorts
        current_time = datetime.now()
        upcoming_sessions = []
        
        if assigned_cohort_ids:
            # Get courses assigned to presenter's cohorts
            cohort_courses = db.query(CohortCourse).filter(
                CohortCourse.cohort_id.in_(assigned_cohort_ids)
            ).all()
            course_ids = [cc.course_id for cc in cohort_courses]
            
            if course_ids:
                upcoming_sessions = db.query(SessionModel).join(
                    Module, SessionModel.module_id == Module.id
                ).join(
                    Course, Module.course_id == Course.id
                ).filter(
                    Course.id.in_(course_ids),
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
        
        if not assigned_cohort_ids:
            # Show all courses when no cohorts assigned
            total_courses = db.query(Course).count()
            total_students = db.query(User).filter(User.role == "Student").count()
            total_modules = db.query(Module).count()
            total_sessions = db.query(SessionModel).count()
            total_enrollments = db.query(Enrollment).count()
            active_enrollments = db.query(Enrollment).filter(Enrollment.progress > 0).count()
            
            return {
                "users": {
                    "total_students": total_students,
                    "total_admins": db.query(Admin).count(),
                    "growth_rate": 12.5
                },
                "courses": {
                    "total_courses": total_courses,
                    "total_modules": total_modules,
                    "total_sessions": total_sessions,
                    "completed_sessions": total_sessions
                },
                "engagement": {
                    "total_enrollments": total_enrollments,
                    "active_enrollments": active_enrollments,
                    "engagement_rate": (active_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0
                },
                "upcoming_sessions": sessions_data,
                "total_upcoming": len(sessions_data)
            }
        
        # User statistics - only students in assigned cohorts
        from database import UserCohort
        total_students = db.query(User).join(UserCohort, User.id == UserCohort.user_id).filter(
            UserCohort.cohort_id.in_(assigned_cohort_ids),
            User.role == "Student"
        ).count()
        
        total_admins = db.query(Admin).count()
        
        # Course statistics - courses assigned to presenter's cohorts
        cohort_courses = db.query(CohortCourse).filter(
            CohortCourse.cohort_id.in_(assigned_cohort_ids)
        ).all() if assigned_cohort_ids else []
        
        course_ids = [cc.course_id for cc in cohort_courses]
        total_courses = len(set(course_ids)) if course_ids else 0
        
        total_modules = db.query(Module).filter(
            Module.course_id.in_(course_ids)
        ).count() if course_ids else 0
        
        total_sessions = db.query(SessionModel).join(
            Module, SessionModel.module_id == Module.id
        ).filter(
            Module.course_id.in_(course_ids)
        ).count() if course_ids else 0
        
        completed_sessions = total_sessions
        
        # Engagement statistics - only for assigned cohorts
        total_enrollments = db.query(Enrollment).filter(
            Enrollment.cohort_id.in_(assigned_cohort_ids)
        ).count() if assigned_cohort_ids else 0
        
        active_enrollments = db.query(Enrollment).filter(
            Enrollment.cohort_id.in_(assigned_cohort_ids),
            Enrollment.progress > 0
        ).count() if assigned_cohort_ids else 0
        
        return {
            "users": {
                "total_students": total_students,
                "total_admins": total_admins,
                "growth_rate": 12.5
            },
            "courses": {
                "total_courses": total_courses,
                "total_modules": total_modules,
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions
            },
            "engagement": {
                "total_enrollments": total_enrollments,
                "active_enrollments": active_enrollments,
                "engagement_rate": (active_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0
            },
            "upcoming_sessions": sessions_data,
            "total_upcoming": len(sessions_data)
        }
    except Exception as e:
        logger.error(f"Presenter dashboard error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard data")

@router.get("/manager/dashboard")
async def get_manager_dashboard(
    current_manager = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Manager dashboard with full system overview and upcoming sessions"""
    try:
        # Get system-wide analytics (managers have full access)
        total_students = db.query(User).filter(User.role == "Student").count()
        total_courses = db.query(Course).count()
        total_sessions = db.query(SessionModel).count()
        total_enrollments = db.query(Enrollment).count()
        total_cohorts = db.query(Cohort).count()
        
        # Get upcoming sessions (all sessions for managers)
        current_time = datetime.now()
        upcoming_sessions = db.query(SessionModel).join(Module, SessionModel.module_id == Module.id).join(Course, Module.course_id == Course.id).filter(
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
            "analytics": {
                "total_students": total_students,
                "total_courses": total_courses,
                "total_sessions": total_sessions,
                "total_enrollments": total_enrollments,
                "total_cohorts": total_cohorts
            },
            "upcoming_sessions": sessions_data,
            "total_upcoming": len(sessions_data)
        }
    except Exception as e:
        logger.error(f"Manager dashboard error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard data")

@router.get("/dashboard/upcoming-sessions")
async def get_upcoming_sessions(
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get upcoming sessions for dashboard - available to all roles"""
    try:
        current_time = datetime.now()
        
        upcoming_sessions = db.query(SessionModel).join(Module).join(Course).filter(
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
            "upcoming_sessions": sessions_data,
            "total": len(sessions_data)
        }
    except Exception as e:
        logger.error(f"Get upcoming sessions error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch upcoming sessions")