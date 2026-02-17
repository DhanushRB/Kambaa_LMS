"""
Email integration helpers for LMS workflows
"""
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from enhanced_email_service import EmailService
from database import User, Course, Assignment, SessionModel, Module
import logging

logger = logging.getLogger(__name__)

def send_user_creation_email(db: Session, user_id: int, background_tasks: BackgroundTasks = None):
    """Send welcome email when user is created"""
    try:
        email_service = EmailService(db)
        return email_service.send_welcome_email(user_id, background_tasks)
    except Exception as e:
        logger.error(f"Failed to send user creation email: {str(e)}")
        return None

def send_enrollment_confirmation_email(db: Session, user_id: int, course_id: int, background_tasks: BackgroundTasks = None):
    """Send enrollment confirmation when user enrolls in course"""
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            return None
        
        email_service = EmailService(db)
        return email_service.send_course_enrollment_email(
            user_id=user_id,
            course_title=course.title,
            course_description=course.description or "No description available",
            background_tasks=background_tasks
        )
    except Exception as e:
        logger.error(f"Failed to send enrollment confirmation email: {str(e)}")
        return None

def send_assignment_creation_emails(db: Session, assignment_id: int, background_tasks: BackgroundTasks = None):
    """Send assignment notification emails to all enrolled students"""
    try:
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not assignment:
            return []
        
        # Get all enrolled students for this course
        from database import Enrollment
        enrollments = db.query(Enrollment).filter(Enrollment.course_id == assignment.course_id).all()
        
        email_service = EmailService(db)
        results = []
        
        for enrollment in enrollments:
            result = email_service.send_assignment_notification(
                user_id=enrollment.student_id,
                assignment_title=assignment.title,
                assignment_description=assignment.description,
                due_date=str(assignment.due_date),
                background_tasks=background_tasks
            )
            if result:
                results.append(result)
        
        return results
    except Exception as e:
        logger.error(f"Failed to send assignment creation emails: {str(e)}")
        return []

def send_session_reminder_emails(db: Session, session_id: int, background_tasks: BackgroundTasks = None):
    """Send session reminder emails to all enrolled students"""
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            return []
        
        # Get course through module
        module = db.query(Module).filter(Module.id == session.module_id).first()
        if not module:
            return []
        
        course = db.query(Course).filter(Course.id == module.course_id).first()
        if not course:
            return []
        
        # Get all enrolled students for this course
        from database import Enrollment
        enrollments = db.query(Enrollment).filter(Enrollment.course_id == course.id).all()
        
        email_service = EmailService(db)
        results = []
        
        for enrollment in enrollments:
            result = email_service.send_session_reminder(
                user_id=enrollment.student_id,
                session_title=session.title,
                course_title=course.title,
                session_time=str(session.scheduled_time),
                duration=session.duration_minutes or 120,
                zoom_link=session.zoom_link,
                background_tasks=background_tasks
            )
            if result:
                results.append(result)
        
        return results
    except Exception as e:
        logger.error(f"Failed to send session reminder emails: {str(e)}")
        return []

def send_certificate_emails(db: Session, user_id: int, course_id: int, background_tasks: BackgroundTasks = None):
    """Send certificate completion email"""
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            return None
        
        email_service = EmailService(db)
        return email_service.send_certificate_email(
            user_id=user_id,
            course_title=course.title,
            background_tasks=background_tasks
        )
    except Exception as e:
        logger.error(f"Failed to send certificate email: {str(e)}")
        return None

def send_bulk_course_notification(db: Session, course_id: int, subject: str, message: str, background_tasks: BackgroundTasks = None):
    """Send bulk notification to all students enrolled in a course"""
    try:
        # Get all enrolled students for this course
        from database import Enrollment
        enrollments = db.query(Enrollment).filter(Enrollment.course_id == course_id).all()
        user_ids = [e.student_id for e in enrollments]
        
        if not user_ids:
            return []
        
        email_service = EmailService(db)
        return email_service.send_bulk_notification(
            user_ids=user_ids,
            subject=subject,
            message=message,
            background_tasks=background_tasks
        )
    except Exception as e:
        logger.error(f"Failed to send bulk course notification: {str(e)}")
        return []

def send_cohort_notification(db: Session, cohort_id: int, subject: str, message: str, background_tasks: BackgroundTasks = None):
    """Send notification to all users in a cohort"""
    try:
        # Get all users in this cohort
        from database import UserCohort
        user_cohorts = db.query(UserCohort).filter(UserCohort.cohort_id == cohort_id).all()
        user_ids = [uc.user_id for uc in user_cohorts]
        
        if not user_ids:
            return []
        
        email_service = EmailService(db)
        return email_service.send_bulk_notification(
            user_ids=user_ids,
            subject=subject,
            message=message,
            background_tasks=background_tasks
        )
    except Exception as e:
        logger.error(f"Failed to send cohort notification: {str(e)}")
        return []