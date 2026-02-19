from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from database import get_db, User, Admin, Presenter, Manager, Mentor, Course, Module, Session as SessionModel, Enrollment, Cohort, UserCohort, CohortCourse, PresenterCohort, Resource, SessionContent
from cohort_specific_models import CohortSpecificCourse, CohortCourseModule, CohortCourseSession
from auth import get_current_admin_or_presenter
from datetime import datetime
from typing import Optional
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/admin/colleges")
async def get_colleges(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get list of unique colleges from users"""
    try:
        colleges = db.query(User.college).filter(User.college.isnot(None)).distinct().all()
        college_list = [college[0] for college in colleges if college[0] and college[0].strip()]
        college_list.sort()
        return {"colleges": college_list}
    except Exception as e:
        logger.error(f"Get colleges error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch colleges")

@router.get("/admin/all-members")
async def get_all_members_comprehensive(
    page: int = 1, 
    limit: int = 50, 
    search: str = "",
    role: str = "",
    college: str = "",
    current_user = Depends(get_current_admin_or_presenter), 
    db: Session = Depends(get_db)
):
    """Get only Admin, Presenter, Manager, and Mentor members"""
    try:
        all_users = []
        
        # Get Admins
        if not role or role == 'Admin':
            admin_query = db.query(Admin)
            if search:
                admin_query = admin_query.filter(
                    or_(
                        Admin.username.contains(search),
                        Admin.email.contains(search)
                    )
                )
            admins = admin_query.all()
            for admin in admins:
                all_users.append({
                    "id": admin.id,
                    "username": admin.username,
                    "email": admin.email,
                    "role": "Admin",
                    "college": None,
                    "department": None,
                    "year": None,
                    "user_type": "Admin",
                    "active": True,
                    "created_at": admin.created_at
                })
        
        # Get Presenters
        if not role or role == 'Presenter':
            presenter_query = db.query(Presenter)
            if search:
                presenter_query = presenter_query.filter(
                    or_(
                        Presenter.username.contains(search),
                        Presenter.email.contains(search)
                    )
                )
            presenters = presenter_query.all()
            for presenter in presenters:
                all_users.append({
                    "id": presenter.id,
                    "username": presenter.username,
                    "email": presenter.email,
                    "role": "Presenter",
                    "college": None,
                    "department": None,
                    "year": None,
                    "user_type": "Presenter",
                    "active": True,
                    "created_at": presenter.created_at
                })
        
        # Get Managers
        if not role or role == 'Manager':
            manager_query = db.query(Manager)
            if search:
                manager_query = manager_query.filter(
                    or_(
                        Manager.username.contains(search),
                        Manager.email.contains(search)
                    )
                )
            managers = manager_query.all()
            for manager in managers:
                all_users.append({
                    "id": manager.id,
                    "username": manager.username,
                    "email": manager.email,
                    "role": "Manager",
                    "college": None,
                    "department": None,
                    "year": None,
                    "user_type": "Manager",
                    "active": True,
                    "created_at": manager.created_at
                })
        
        # Get Mentors
        if not role or role == 'Mentor':
            mentor_query = db.query(Mentor)
            if search:
                mentor_query = mentor_query.filter(
                    or_(
                        Mentor.username.contains(search),
                        Mentor.email.contains(search)
                    )
                )
            mentors = mentor_query.all()
            for mentor in mentors:
                all_users.append({
                    "id": mentor.id,
                    "username": mentor.username,
                    "email": mentor.email,
                    "role": "Mentor",
                    "college": None,
                    "department": None,
                    "year": None,
                    "user_type": "Mentor",
                    "active": True,
                    "created_at": mentor.created_at
                })
        
        # Sort by created_at (most recent first)
        try:
            all_users.sort(key=lambda x: x['created_at'] if isinstance(x['created_at'], datetime) else datetime.now(), reverse=True)
        except (TypeError, AttributeError):
            all_users.sort(key=lambda x: x['username'])
        
        # Apply pagination
        total = len(all_users)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_users = all_users[start_idx:end_idx]
        
        return {
            "users": paginated_users,
            "total": total,
            "page": page,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Get all members error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch all members")

@router.get("/admin/courses")
async def get_admin_courses(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    is_active: Optional[str] = None,
    current_user = Depends(get_current_admin_or_presenter), 
    db: Session = Depends(get_db)
):
    try:
        query = db.query(Course)
        
        if search:
            query = query.filter(
                or_(
                    Course.title.contains(search),
                    Course.description.contains(search)
                )
            )
        
        if is_active and is_active.lower() in ['true', 'false']:
            query = query.filter(Course.is_active == (is_active.lower() == 'true'))
        
        total = query.count()
        courses = query.offset((page - 1) * limit).limit(limit).all()
        
        result = []
        for course in courses:
            enrolled_count = db.query(Enrollment).filter(Enrollment.course_id == course.id).count()
            modules_count = db.query(Module).filter(Module.course_id == course.id).count()
            
            result.append({
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "duration_weeks": course.duration_weeks,
                "sessions_per_week": course.sessions_per_week,
                "is_active": course.is_active,
                "enrolled_students": enrolled_count,
                "modules_count": modules_count,
                "created_at": course.created_at
            })
        
        return {
            "courses": result,
            "total": total,
            "page": page,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Get courses error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch courses")

@router.get("/admin/course/{course_id}")
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

@router.get("/admin/modules")
async def get_course_modules(
    course_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        # First check if it's a regular course
        modules = db.query(Module).filter(Module.course_id == course_id).order_by(Module.week_number).all()
        
        if not modules:
            # Check if it's a cohort-specific course
            modules = db.query(CohortCourseModule).filter(CohortCourseModule.course_id == course_id).order_by(CohortCourseModule.week_number).all()
            is_cohort = True
        else:
            is_cohort = False
            
        result = []
        for module in modules:
            if is_cohort:
                sessions = db.query(CohortCourseSession).filter(CohortCourseSession.module_id == module.id).order_by(CohortCourseSession.session_number).all()
            else:
                sessions = db.query(SessionModel).filter(SessionModel.module_id == module.id).order_by(SessionModel.session_number).all()
            
            result.append({
                "id": module.id,
                "week_number": module.week_number,
                "title": module.title,
                "description": module.description,
                "start_date": module.start_date,
                "end_date": module.end_date,
                "sessions_count": len(sessions),
                "created_at": module.created_at,
                "is_cohort_specific": is_cohort,
                "sessions": [{
                    "id": s.id,
                    "session_number": s.session_number,
                    "title": s.title,
                    "scheduled_time": s.scheduled_time,
                    "duration_minutes": s.duration_minutes
                } for s in sessions]
            })
        
        return {"modules": result}
    except Exception as e:
        logger.error(f"Get course modules error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch modules")

@router.get("/admin/sessions")
async def get_module_sessions(
    module_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        # First check regular sessions
        sessions = db.query(SessionModel).filter(SessionModel.module_id == module_id).order_by(SessionModel.session_number).all()
        is_cohort = False
        
        if not sessions:
            # Check cohort-specific sessions
            sessions = db.query(CohortCourseSession).filter(CohortCourseSession.module_id == module_id).order_by(CohortCourseSession.session_number).all()
            is_cohort = True
            
        result = []
        for session in sessions:
            result.append({
                "id": session.id,
                "session_number": session.session_number,
                "title": session.title,
                "description": session.description,
                "scheduled_time": session.scheduled_time,
                "duration_minutes": session.duration_minutes,
                "zoom_link": session.zoom_link,
                "recording_url": session.recording_url,
                "is_cohort_specific": is_cohort,
                "created_at": session.created_at
            })
        
        return result
    except Exception as e:
        logger.error(f"Get module sessions error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch sessions")


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

@router.get("/admin/recent-activity")
async def get_admin_recent_activity(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get recent activity for admin dashboard"""
    try:
        from assignment_quiz_models import Assignment, Quiz, QuizAttempt, AssignmentSubmission
        from cohort_specific_models import CohortSpecificCourse
        
        activities = []
        
        from datetime import timedelta
        
        # Calculate 30 days ago
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        # Recent course creations (last 30 days)
        recent_courses = db.query(Course).filter(
            Course.created_at >= thirty_days_ago
        ).order_by(Course.created_at.desc()).limit(5).all()
        
        for course in recent_courses:
            time_diff = datetime.now() - course.created_at
            activities.append({
                "type": "course_created",
                "title": f'New course "{course.title}" created',
                "description": f"Course created with {course.duration_weeks} weeks duration",
                "time_ago": format_time_ago(time_diff),
                "timestamp": course.created_at
            })
        
        # Recent cohort course creations
        recent_cohort_courses = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.created_at >= thirty_days_ago
        ).order_by(CohortSpecificCourse.created_at.desc()).limit(5).all()
        
        for course in recent_cohort_courses:
            time_diff = datetime.now() - course.created_at
            activities.append({
                "type": "cohort_course_created",
                "title": f'New cohort course "{course.title}" created',
                "description": f"Cohort-specific course created",
                "time_ago": format_time_ago(time_diff),
                "timestamp": course.created_at
            })
        
        # Recent student registrations
        recent_students = db.query(User).filter(
            User.role == "Student",
            User.created_at >= thirty_days_ago
        ).order_by(User.created_at.desc()).limit(5).all()
        
        for student in recent_students:
            time_diff = datetime.now() - student.created_at
            activities.append({
                "type": "student_registered",
                "title": "New student registered",
                "description": f"{student.username} joined the platform",
                "time_ago": format_time_ago(time_diff),
                "timestamp": student.created_at
            })
        
        # Recent presenter registrations
        recent_presenters = db.query(Presenter).filter(
            Presenter.created_at >= thirty_days_ago
        ).order_by(Presenter.created_at.desc()).limit(3).all()
        
        for presenter in recent_presenters:
            time_diff = datetime.now() - presenter.created_at
            activities.append({
                "type": "presenter_registered",
                "title": "New presenter registered",
                "description": f"{presenter.username} joined as presenter",
                "time_ago": format_time_ago(time_diff),
                "timestamp": presenter.created_at
            })
        
        # Recent mentor registrations
        recent_mentors = db.query(Mentor).filter(
            Mentor.created_at >= thirty_days_ago
        ).order_by(Mentor.created_at.desc()).limit(3).all()
        
        for mentor in recent_mentors:
            time_diff = datetime.now() - mentor.created_at
            activities.append({
                "type": "mentor_registered",
                "title": "New mentor registered",
                "description": f"{mentor.username} joined as mentor",
                "time_ago": format_time_ago(time_diff),
                "timestamp": mentor.created_at
            })
        
        # Sort all activities by timestamp
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return {"activities": activities[:10]}
        
    except Exception as e:
        logger.error(f"Admin recent activity error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch recent activity")

@router.get("/admin/recent-meeting-links")
async def get_recent_meeting_links(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get the most recent meeting links across all sessions for admin dashboard"""
    try:
        # Fetch regular meeting links
        regular_rows = (
            db.query(SessionContent, SessionModel.title.label("session_title"))
            .join(SessionModel, SessionContent.session_id == SessionModel.id)
            .filter(
                SessionContent.content_type == "MEETING_LINK",
                SessionContent.meeting_url.isnot(None),
                SessionContent.meeting_url != ""
            )
            .order_by(SessionContent.created_at.desc())
            .limit(10)
            .all()
        )

        # Fetch cohort-specific meeting links
        cohort_rows = (
            db.query(CohortSessionContent, CohortCourseSession.title.label("session_title"))
            .join(CohortCourseSession, CohortSessionContent.session_id == CohortCourseSession.id)
            .filter(
                CohortSessionContent.content_type == "MEETING_LINK",
                CohortSessionContent.meeting_url.isnot(None),
                CohortSessionContent.meeting_url != ""
            )
            .order_by(CohortSessionContent.created_at.desc())
            .limit(10)
            .all()
        )

        result = []
        for content, session_title in regular_rows:
            result.append({
                "id": content.id,
                "title": content.title or "Meeting Link",
                "session_title": session_title,
                "meeting_url": content.meeting_url,
                "scheduled_time": content.scheduled_time.isoformat() if content.scheduled_time else None,
                "created_at": content.created_at.isoformat() if content.created_at else None,
                "content_type": content.content_type,
                "is_cohort_specific": False
            })

        for content, session_title in cohort_rows:
            result.append({
                "id": f"cohort_{content.id}",
                "title": content.title or "Meeting Link",
                "session_title": session_title,
                "meeting_url": content.meeting_url,
                "scheduled_time": content.scheduled_time.isoformat() if content.scheduled_time else None,
                "created_at": content.created_at.isoformat() if content.created_at else None,
                "content_type": content.content_type,
                "is_cohort_specific": True
            })

        # Sort combined results by created_at desc and limit to 10
        result.sort(key=lambda x: x["created_at"] or "", reverse=True)
        result = result[:10]

        return {"meetings": result}
    except Exception as e:
        logger.error(f"Get recent meeting links error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch meeting links")


def format_time_ago(time_diff):
    """Format time difference to human readable string"""
    days = time_diff.days
    hours = time_diff.seconds // 3600
    minutes = (time_diff.seconds % 3600) // 60
    
    if days > 0:
        return f"{days} day{'s' if days > 1 else ''} ago"
    elif hours > 0:
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif minutes > 0:
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"