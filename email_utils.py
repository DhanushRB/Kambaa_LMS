from sqlalchemy.orm import Session
from database import EmailTemplate, User, UserCohort, Cohort
from datetime import datetime
from notification_service import NotificationService
import logging

logger = logging.getLogger(__name__)

async def send_course_added_notification(
    db: Session,
    cohort_id: int,
    course_title: str,
    course_description: str = "",
    duration_weeks: int = 0,
    sessions_per_week: int = 0
):
    """Send email notification to all students in cohort when a course is added"""
    try:
        # Get the course added template
        template = db.query(EmailTemplate).filter(
            EmailTemplate.name == "New Course Added to Cohort",
            EmailTemplate.is_active == True
        ).first()
        
        if not template:
            logger.warning("Course added template not found or disabled")
            return
        
        # Get cohort details
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            logger.error(f"Cohort {cohort_id} not found")
            return
        
        # Get all students in the cohort
        user_cohorts = db.query(UserCohort).join(User).filter(
            UserCohort.cohort_id == cohort_id,
            User.user_type == "Student"
        ).all()
        
        if not user_cohorts:
            logger.info(f"No students found in cohort {cohort_id}")
            return
        
        # Initialize notification service
        notification_service = NotificationService(db)
        
        # Send email to each student
        for uc in user_cohorts:
            user = uc.user
            try:
                # Format email content
                subject = template.subject.format(course_title=course_title)
                body_text = template.body.format(
                    username=user.username,
                    course_title=course_title,
                    course_description=course_description or "No description available",
                    duration_weeks=duration_weeks,
                    sessions_per_week=sessions_per_week,
                    cohort_name=cohort.name,
                    added_date=datetime.now().strftime("%B %d, %Y")
                )
                
                # Convert plain text to HTML format
                body_html = body_text.replace('\n', '<br>').replace('\n\n', '<br><br>')
                
                # Send email using notification service
                email_log = notification_service.send_email_notification(
                    user_id=user.id,
                    email=user.email,
                    subject=subject,
                    body=body_html
                )
                
                logger.info(f"Sending course notification to {user.email}: {subject}")
                logger.info(f"Email status: {email_log.status}")
                if email_log.error_message:
                    logger.error(f"Email error for {user.email}: {email_log.error_message}")
                
            except Exception as e:
                logger.error(f"Failed to send email to {user.email}: {str(e)}")
                continue
        
        logger.info(f"Course notification sent to {len(user_cohorts)} students in cohort {cohort.name}")
        
    except Exception as e:
        logger.error(f"Failed to send course added notifications: {str(e)}")
async def send_course_enrollment_confirmation(
    db: Session,
    user_id: int,
    course_title: str,
    course_description: str = "",
    duration_weeks: int = 0,
    sessions_per_week: int = 0,
    course_start_date: str = "TBD"
):
    """Send email confirmation when a student enrolls in a course"""
    try:
        # Get the enrollment confirmation template
        template = db.query(EmailTemplate).filter(
            EmailTemplate.name == "Course Enrollment Confirmation",
            EmailTemplate.is_active == True
        ).first()
        
        if not template:
            logger.warning("Course enrollment confirmation template not found or disabled")
            return
        
        # Get user details
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User {user_id} not found")
            return
        
        # Initialize notification service
        notification_service = NotificationService(db)
        
        try:
            # Format email content
            subject = template.subject.format(course_title=course_title)
            body_text = template.body.format(
                username=user.username,
                course_title=course_title,
                course_description=course_description or "No description available",
                duration_weeks=duration_weeks,
                sessions_per_week=sessions_per_week,
                enrollment_date=datetime.now().strftime("%B %d, %Y"),
                course_start_date=course_start_date
            )
            
            # Convert plain text to HTML format
            body_html = body_text.replace('\n', '<br>').replace('\n\n', '<br><br>')
            
            # Send email using notification service
            email_log = notification_service.send_email_notification(
                user_id=user.id,
                email=user.email,
                subject=subject,
                body=body_html
            )
            
            logger.info(f"Sending enrollment confirmation to {user.email}: {subject}")
            logger.info(f"Email status: {email_log.status}")
            if email_log.error_message:
                logger.error(f"Email error for {user.email}: {email_log.error_message}")
            
        except Exception as e:
            logger.error(f"Failed to send enrollment confirmation to {user.email}: {str(e)}")
        
    except Exception as e:
        logger.error(f"Failed to send course enrollment confirmation: {str(e)}")