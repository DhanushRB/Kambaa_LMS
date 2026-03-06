from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import (
    get_db, User, Admin, Presenter, Course, Module, Session as SessionModel, 
    Enrollment, Cohort, UserCohort, CohortCourse, PresenterCohort, Resource, 
    StudentSessionStatus, StudentModuleStatus, Attendance
)
from assignment_quiz_models import Quiz, Assignment
from cohort_specific_models import CohortSpecificCourse, CohortCourseSession, CohortCourseModule, CohortCourseResource
from auth import get_current_presenter
from datetime import datetime, timedelta
import logging

router = APIRouter(prefix="/presenter", tags=["presenter_dashboard"])
logger = logging.getLogger(__name__)

@router.get("/dashboard")
async def get_presenter_dashboard(
    current_presenter: Presenter = Depends(get_current_presenter),
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
            # 1. Get global courses assigned to presenter's cohorts
            cohort_courses = db.query(CohortCourse).filter(
                CohortCourse.cohort_id.in_(assigned_cohort_ids)
            ).all()
            global_course_ids = [cc.course_id for cc in cohort_courses]
            
            # 2. Get sessions for global courses
            if global_course_ids:
                global_sessions = db.query(SessionModel).join(
                    Module, SessionModel.module_id == Module.id
                ).filter(
                    Module.course_id.in_(global_course_ids),
                    SessionModel.scheduled_time.isnot(None),
                    SessionModel.scheduled_time > current_time
                ).all()
                upcoming_sessions.extend(global_sessions)
            
            # 3. Get sessions for cohort-specific courses
            from cohort_specific_models import CohortCourseSession, CohortCourseModule
            cohort_specific_sessions = db.query(CohortCourseSession).join(
                CohortCourseModule, CohortCourseSession.module_id == CohortCourseModule.id
            ).join(
                CohortSpecificCourse, CohortCourseModule.course_id == CohortSpecificCourse.id
            ).filter(
                CohortSpecificCourse.cohort_id.in_(assigned_cohort_ids),
                CohortCourseSession.scheduled_time.isnot(None),
                CohortCourseSession.scheduled_time > current_time
            ).all()
            upcoming_sessions.extend(cohort_specific_sessions)

        # Sort combined sessions and limit
        upcoming_sessions.sort(key=lambda s: s.scheduled_time)
        upcoming_sessions = upcoming_sessions[:10]
        
        sessions_data = []
        for session in upcoming_sessions:
            # Handle both global and cohort-specific sessions
            is_cohort_specific = hasattr(session, 'module') and hasattr(session.module, 'course') and isinstance(session.module.course, CohortSpecificCourse)
            
            if is_cohort_specific:
                module = session.module
                course = module.course
            else:
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
                "zoom_link": getattr(session, 'zoom_link', None),
                "session_number": session.session_number,
                "week_number": module.week_number if module else None,
                "is_cohort_specific": is_cohort_specific
            })
        
        if not assigned_cohort_ids:
            # Fast return for unassigned presenters
            return {
                "users": {"total_students": 0, "total_admins": db.query(Admin).count(), "growth_rate": 0},
                "courses": {"total_courses": 0, "total_modules": 0, "total_sessions": 0, "completed_sessions": 0},
                "engagement": {"total_enrollments": 0, "active_enrollments": 0, "engagement_rate": 0, "total_resources": 0},
                "performance": {"attendance_rate": 0, "completion_rate": 0, "average_quiz_score": 0},
                "upcoming_sessions": [], "total_upcoming": 0
            }
        
        # --- AGGREGATE STATS ---
        
        # Students in assigned cohorts (Checking both UserCohort and User.cohort_id)
        total_students = db.query(func.count(func.distinct(User.id))).outerjoin(UserCohort, User.id == UserCohort.user_id).filter(
            or_(
                UserCohort.cohort_id.in_(assigned_cohort_ids),
                User.cohort_id.in_(assigned_cohort_ids)
            ),
            User.role == "Student"
        ).scalar() or 0
        
        # Course counts (Global assigned to cohorts + CohortSpecific)
        global_courses_count = db.query(func.count(func.distinct(CohortCourse.course_id))).filter(
            CohortCourse.cohort_id.in_(assigned_cohort_ids)
        ).scalar() or 0
        
        cohort_specific_courses_count = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.cohort_id.in_(assigned_cohort_ids)
        ).count()
        
        total_courses = global_courses_count + cohort_specific_courses_count
        
        # Modules and Sessions (Combined)
        total_modules = db.query(Module).filter(Module.course_id.in_(global_course_ids)).count() if global_course_ids else 0
        total_modules += db.query(CohortCourseModule).join(CohortSpecificCourse).filter(
            CohortSpecificCourse.cohort_id.in_(assigned_cohort_ids)
        ).count()
        
        total_sessions = db.query(SessionModel).join(Module).filter(Module.course_id.in_(global_course_ids)).count() if global_course_ids else 0
        total_sessions += db.query(CohortCourseSession).join(CohortCourseModule).join(CohortSpecificCourse).filter(
            CohortSpecificCourse.cohort_id.in_(assigned_cohort_ids)
        ).count()
        
        # Resource counts
        total_resources = db.query(Resource).join(SessionModel).join(Module).filter(Module.course_id.in_(global_course_ids)).count() if global_course_ids else 0
        total_resources += db.query(CohortCourseResource).join(CohortCourseSession).join(CohortCourseModule).join(CohortSpecificCourse).filter(
            CohortSpecificCourse.cohort_id.in_(assigned_cohort_ids)
        ).count()
        
        # Quiz counts
        # 1. Global sessions quizzes
        global_sessions_ids = [s.id for s in db.query(SessionModel.id).join(Module).filter(Module.course_id.in_(global_course_ids)).all()] if global_course_ids else []
        total_quizzes = db.query(Quiz).filter(
            Quiz.session_type == "global",
            Quiz.session_id.in_(global_sessions_ids)
        ).count() if global_sessions_ids else 0
        
        # 2. Cohort specific sessions quizzes
        cohort_sessions_ids = [s.id for s in db.query(CohortCourseSession.id).join(CohortCourseModule).join(CohortSpecificCourse).filter(
            CohortSpecificCourse.cohort_id.in_(assigned_cohort_ids)
        ).all()]
        total_quizzes += db.query(Quiz).filter(
            Quiz.session_type == "cohort",
            Quiz.session_id.in_(cohort_sessions_ids)
        ).count() if cohort_sessions_ids else 0
        
        # Enrollment stats
        total_enrollments = db.query(Enrollment).filter(Enrollment.cohort_id.in_(assigned_cohort_ids)).count()
        if total_enrollments == 0:
            total_enrollments = total_students # Student count as proxy if enrollment empty
            
        active_enrollments = db.query(Enrollment).filter(Enrollment.cohort_id.in_(assigned_cohort_ids), Enrollment.progress > 0).count()
        if active_enrollments == 0:
            # Check progress tables if enrollment doesn't track it
            active_enrollments = db.query(func.count(func.distinct(StudentModuleStatus.student_id))).outerjoin(UserCohort, StudentModuleStatus.student_id == UserCohort.user_id).outerjoin(User, StudentModuleStatus.student_id == User.id).filter(
                or_(UserCohort.cohort_id.in_(assigned_cohort_ids), User.cohort_id.in_(assigned_cohort_ids))
            ).scalar() or 0
        
        # Performance rates
        avg_attendance = db.query(func.avg(StudentSessionStatus.progress_percentage)).outerjoin(UserCohort, StudentSessionStatus.student_id == UserCohort.user_id).outerjoin(User, StudentSessionStatus.student_id == User.id).filter(
            or_(UserCohort.cohort_id.in_(assigned_cohort_ids), User.cohort_id.in_(assigned_cohort_ids))
        ).scalar() or 0
        
        avg_completion = db.query(func.avg(StudentModuleStatus.progress_percentage)).outerjoin(UserCohort, StudentModuleStatus.student_id == UserCohort.user_id).outerjoin(User, StudentModuleStatus.student_id == User.id).filter(
            or_(UserCohort.cohort_id.in_(assigned_cohort_ids), User.cohort_id.in_(assigned_cohort_ids))
        ).scalar() or 0
        
        return {
            "users": {
                "total_students": total_students,
                "total_admins": db.query(Admin).count(),
                "growth_rate": 0
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
                "engagement_rate": (active_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0,
                "total_resources": total_resources,
                "total_quizzes": total_quizzes
            },
            "performance": {
                "attendance_rate": round(float(avg_attendance), 2),
                "completion_rate": round(float(avg_completion), 2),
                "average_quiz_score": 0,
                "target_attendance": 80.0,
                "target_completion": 90.0
            },
            "upcoming_sessions": sessions_data,
            "total_upcoming": len(sessions_data)
        }
    except Exception as e:
        logger.error(f"Presenter dashboard error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch dashboard data: {str(e)}")

@router.get("/github-stats")
async def get_presenter_github_stats(
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    """Get GitHub link submission statistics for students in presenter's cohorts"""
    try:
        # Get cohorts assigned to this presenter
        presenter_cohorts = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == current_presenter.id
        ).all()
        assigned_cohort_ids = [pc.cohort_id for pc in presenter_cohorts]
        
        if not assigned_cohort_ids:
            return {"total_students": 0, "students_with_github": 0, "percentage": 0}

        from sqlalchemy import or_
        # Filter students by assigned cohorts (checking both mapping table and direct field)
        student_query = db.query(User).outerjoin(UserCohort, User.id == UserCohort.user_id).filter(
            or_(
                UserCohort.cohort_id.in_(assigned_cohort_ids),
                User.cohort_id.in_(assigned_cohort_ids)
            ),
            User.role == "Student"
        )
        
        total_students = student_query.count()
        
        # Count students with GitHub links
        students_with_github = student_query.filter(
            User.github_link.isnot(None),
            User.github_link != ""
        ).count()
        
        # Calculate percentage
        percentage = round((students_with_github / total_students * 100), 1) if total_students > 0 else 0
        
        return {
            "total_students": total_students,
            "students_with_github": students_with_github,
            "percentage": percentage
        }
    except Exception as e:
        logger.error(f"Presenter GitHub stats error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch GitHub statistics")

@router.get("/recent-activity")
async def get_presenter_recent_activity(
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    """Get recent activity for presenter dashboard"""
    try:
        from assignment_quiz_models import Assignment, Quiz, QuizAttempt, AssignmentSubmission
        from cohort_specific_models import CohortSpecificCourse
        
        # Get presenter's assigned cohorts
        presenter_cohorts = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == current_presenter.id
        ).all()
        assigned_cohort_ids = [pc.cohort_id for pc in presenter_cohorts]
        
        activities = []
        
        # Recent cohort course creations by this presenter
        recent_cohort_courses = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.created_by == current_presenter.id,
            CohortSpecificCourse.created_at >= datetime.now() - timedelta(days=30)
        ).order_by(CohortSpecificCourse.created_at.desc()).limit(3).all()
        
        for course in recent_cohort_courses:
            time_diff = datetime.now() - course.created_at
            activities.append({
                "type": "course_created",
                "title": f'New course "{course.title}" created',
                "description": f"Cohort course created with {course.duration_weeks} weeks duration",
                "time_ago": format_time_ago(time_diff),
                "timestamp": course.created_at
            })
        
        if assigned_cohort_ids:
            # Recent student activity in presenter's cohorts
            recent_quiz_attempts = db.query(QuizAttempt).join(
                User, QuizAttempt.student_id == User.id
            ).filter(
                User.cohort_id.in_(assigned_cohort_ids),
                QuizAttempt.submitted_at >= datetime.now() - timedelta(days=7)
            ).order_by(QuizAttempt.submitted_at.desc()).limit(5).all()
            
            for attempt in recent_quiz_attempts:
                student = db.query(User).filter(User.id == attempt.student_id).first()
                quiz = db.query(Quiz).filter(Quiz.id == attempt.quiz_id).first()
                time_diff = datetime.now() - attempt.submitted_at
                
                activities.append({
                    "type": "quiz_submitted",
                    "title": f"Quiz submitted by {student.username if student else 'Unknown'}",
                    "description": f"Quiz '{quiz.title if quiz else 'Unknown'}' completed",
                    "time_ago": format_time_ago(time_diff),
                    "timestamp": attempt.submitted_at
                })
            
            # Recent assignment submissions
            recent_assignments = db.query(AssignmentSubmission).join(
                User, AssignmentSubmission.student_id == User.id
            ).filter(
                User.cohort_id.in_(assigned_cohort_ids),
                AssignmentSubmission.submitted_at >= datetime.now() - timedelta(days=7)
            ).order_by(AssignmentSubmission.submitted_at.desc()).limit(5).all()
            
            for submission in recent_assignments:
                student = db.query(User).filter(User.id == submission.student_id).first()
                assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
                time_diff = datetime.now() - submission.submitted_at
                
                activities.append({
                    "type": "assignment_submitted",
                    "title": f"Assignment submitted by {student.username if student else 'Unknown'}",
                    "description": f"Assignment '{assignment.title if assignment else 'Unknown'}' submitted",
                    "time_ago": format_time_ago(time_diff),
                    "timestamp": submission.submitted_at
                })
            
            # Recent student enrollments in presenter's cohorts
            recent_students = db.query(User).filter(
                User.role == "Student",
                User.cohort_id.in_(assigned_cohort_ids),
                User.created_at >= datetime.now() - timedelta(days=30)
            ).order_by(User.created_at.desc()).limit(3).all()
            
            for student in recent_students:
                cohort = db.query(Cohort).filter(Cohort.id == student.cohort_id).first()
                time_diff = datetime.now() - student.created_at
                
                activities.append({
                    "type": "student_joined",
                    "title": f"New student joined cohort",
                    "description": f"{student.username} joined {cohort.name if cohort else 'cohort'}",
                    "time_ago": format_time_ago(time_diff),
                    "timestamp": student.created_at
                })
        
        # Sort all activities by timestamp
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return {"activities": activities[:10]}
        
    except Exception as e:
        logger.error(f"Presenter recent activity error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch recent activity")

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