from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db, User, Course, Module, Session as SessionModel, Enrollment, Cohort, MentorCohort, MentorCourse, MentorSession
from auth import get_current_mentor
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/mentor/dashboard")
async def get_mentor_dashboard(
    current_mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    """Mentor dashboard with mentor-specific data"""
    try:
        # Get mentor's assigned cohorts
        mentor_cohorts = db.query(MentorCohort).filter(
            MentorCohort.mentor_id == current_mentor.id
        ).all()
        
        assigned_cohort_ids = [mc.cohort_id for mc in mentor_cohorts]
        
        # Get mentor's assigned courses
        mentor_courses = db.query(MentorCourse).filter(
            MentorCourse.mentor_id == current_mentor.id
        ).all()
        
        assigned_course_ids = [mc.course_id for mc in mentor_courses]
        
        # Get mentor's assigned sessions
        mentor_sessions = db.query(MentorSession).filter(
            MentorSession.mentor_id == current_mentor.id
        ).all()
        
        assigned_session_ids = [ms.session_id for ms in mentor_sessions]
        
        # Get upcoming sessions for mentor
        current_time = datetime.now()
        upcoming_sessions = []
        
        if assigned_session_ids:
            upcoming_sessions = db.query(SessionModel).filter(
                SessionModel.id.in_(assigned_session_ids),
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
        
        # Get statistics for mentor's assigned resources
        total_students = 0
        if assigned_cohort_ids:
            total_students = db.query(User).join(
                "user_cohorts"
            ).filter(
                User.role == "Student"
            ).count()
        
        total_courses = len(assigned_course_ids)
        total_sessions = len(assigned_session_ids)
        total_cohorts = len(assigned_cohort_ids)
        
        return {
            "analytics": {
                "total_students": total_students,
                "total_courses": total_courses,
                "total_sessions": total_sessions,
                "total_cohorts": total_cohorts,
                "assigned_cohorts": len(assigned_cohort_ids),
                "assigned_courses": len(assigned_course_ids),
                "assigned_sessions": len(assigned_session_ids)
            },
            "upcoming_sessions": sessions_data,
            "total_upcoming": len(sessions_data)
        }
    except Exception as e:
        logger.error(f"Mentor dashboard error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard data")

@router.get("/mentor/recent-activity")
async def get_mentor_recent_activity(
    current_mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    """Get recent student activity for mentor dashboard"""
    try:
        from assignment_quiz_models import Assignment, Quiz, QuizAttempt, AssignmentSubmission
        
        # Get mentor's assigned cohorts
        mentor_cohorts = db.query(MentorCohort).filter(
            MentorCohort.mentor_id == current_mentor.id
        ).all()
        assigned_cohort_ids = [mc.cohort_id for mc in mentor_cohorts]
        
        activities = []
        
        if assigned_cohort_ids:
            # Recent quiz submissions from students in mentor's cohorts
            recent_quiz_attempts = db.query(QuizAttempt).join(
                User, QuizAttempt.student_id == User.id
            ).filter(
                User.cohort_id.in_(assigned_cohort_ids),
                QuizAttempt.submitted_at >= datetime.now() - func.interval('7 days')
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
            
            # Recent assignment submissions from students in mentor's cohorts
            recent_assignments = db.query(AssignmentSubmission).join(
                User, AssignmentSubmission.student_id == User.id
            ).filter(
                User.cohort_id.in_(assigned_cohort_ids),
                AssignmentSubmission.submitted_at >= datetime.now() - func.interval('7 days')
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
            
            # Recent module completions (simulated based on enrollments)
            recent_enrollments = db.query(Enrollment).join(
                User, Enrollment.student_id == User.id
            ).filter(
                User.cohort_id.in_(assigned_cohort_ids),
                Enrollment.progress > 0,
                Enrollment.updated_at >= datetime.now() - func.interval('7 days')
            ).order_by(Enrollment.updated_at.desc()).limit(3).all()
            
            for enrollment in recent_enrollments:
                student = db.query(User).filter(User.id == enrollment.student_id).first()
                course = db.query(Course).filter(Course.id == enrollment.course_id).first()
                time_diff = datetime.now() - enrollment.updated_at
                
                # Simulate module completion based on progress
                module_number = min(int(enrollment.progress / 25) + 1, 4)
                
                activities.append({
                    "type": "module_completed",
                    "title": f"Student {student.username if student else 'Unknown'} completed Module {module_number}",
                    "description": f"Progress in {course.title if course else 'Unknown Course'}",
                    "time_ago": format_time_ago(time_diff),
                    "timestamp": enrollment.updated_at
                })
        
        # Sort all activities by timestamp
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return {"activities": activities[:10]}
        
    except Exception as e:
        logger.error(f"Mentor recent activity error: {str(e)}")
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