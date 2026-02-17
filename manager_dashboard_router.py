from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db, User, Course, Module, Session as SessionModel, Enrollment, Cohort
from auth import get_current_admin_presenter_mentor_or_manager
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

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