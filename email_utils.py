from database import EmailTemplate, User, UserCohort, Cohort, Enrollment, Module, Session, SessionContent
from cohort_specific_models import CohortSpecificCourse, CohortCourseModule, CohortCourseSession
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
            
        except Exception as e:
            logger.error(f"Failed to send enrollment confirmation to {user.email}: {str(e)}")
            
    except Exception as e:
        logger.error(f"Failed to send course enrollment confirmation: {str(e)}")

async def send_content_added_notification(
    db: Session,
    session_id: int,
    content_title: str,
    content_type: str,
    session_type: str = "global",
    description: str = ""
):
    """
    Send email notification to all students when new content (resource, assignment, quiz) is added.
    
    Args:
        db: Database session
        session_id: ID of the session the content was added to
        content_title: Title of the new content
        content_type: Type of content (RESOURCE, ASSIGNMENT, QUIZ, etc.)
        session_type: "global" or "cohort"
        description: Description of the content
    """
    try:
            
        # 1. Get the template
        template = db.query(EmailTemplate).filter(
            EmailTemplate.name == "New Resource Added Notification",
            EmailTemplate.is_active == True
        ).first()
        
        if not template:
            logger.warning("Resource added template not found or disabled")
            return

        # 2. Get session, module, and course details
        course_title = "Unknown Course"
        module_title = "Unknown Module"
        session_title = "Unknown Session"
        target_students = []
        course_id = None

        if session_type == "cohort":
            cohort_session = db.query(CohortCourseSession).filter(CohortCourseSession.id == session_id).first()
            if cohort_session:
                session_title = cohort_session.title
                cohort_module = db.query(CohortCourseModule).filter(CohortCourseModule.id == cohort_session.module_id).first()
                if cohort_module:
                    module_title = cohort_module.title
                    cohort_course = db.query(CohortSpecificCourse).filter(CohortSpecificCourse.id == cohort_module.course_id).first()
                    if cohort_course:
                        course_title = cohort_course.title
                        # For cohort courses, notify all students in the cohort
                        target_students = db.query(User).join(UserCohort).filter(
                            UserCohort.cohort_id == cohort_course.cohort_id,
                            User.user_type == "Student",
                            User.role == "Student"
                        ).all()
                        logger.info(f"Cohort {cohort_course.cohort_id} has {len(target_students)} eligible students")
        else:
            regular_session = db.query(Session).filter(Session.id == session_id).first()
            if regular_session:
                session_title = regular_session.title
                regular_module = db.query(Module).filter(Module.id == regular_session.module_id).first()
                if regular_module:
                    module_title = regular_module.title
                    from database import Course
                    regular_course = db.query(Course).filter(Course.id == regular_module.course_id).first()
                    if regular_course:
                        course_title = regular_course.title
                        course_id = regular_course.id
                        # For global courses, notify enrolled students
                        target_students = db.query(User).join(Enrollment).filter(
                            Enrollment.course_id == course_id,
                            User.user_type == "Student",
                            User.role == "Student"
                        ).all()
                        logger.info(f"Global Course {course_id} has {len(target_students)} eligible students")
                        logger.info(f"Global course {course_id} has {len(target_students)} eligible students")

        if not target_students:
            with open("notification_debug.log", "a") as f:
                f.write(f"[{datetime.now()}] NO STUDENTS FOUND\n")
            logger.info(f"No students found to notify for session {session_id}")
            return

        # 3. Initialize notification service
        notification_service = NotificationService(db)
        
        # 4. Send emails
        added_date = datetime.now().strftime("%B %d, %Y")
        success_count = 0
        
        for student in target_students:
            try:
                # Format placeholders
                context = {
                    "username": student.username,
                    "resource_title": content_title,
                    "course_title": course_title,
                    "module_title": module_title,
                    "session_title": session_title,
                    "resource_type": content_type,
                    "resource_description": description or "No description provided",
                    "added_date": added_date
                }
                
                subject = template.subject.format(**context)
                body_text = template.body.format(**context)
                
                # Convert plain text to HTML format
                body_html = body_text.replace('\n', '<br>').replace('\n\n', '<br><br>')
                
                # Send email
                notification_service.send_email_notification(
                    user_id=student.id,
                    email=student.email,
                    subject=subject,
                    body=body_html
                )
                success_count += 1
                logger.info(f"Successfully sent notification to {student.email}")
                
            except Exception as e:
                logger.error(f"Failed to send resource notification to {student.email}: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                continue
                
        logger.info(f"Content notification sent to {success_count}/{len(target_students)} students")
        
    except Exception as e:
        logger.error(f"Failed to send content added notifications: {str(e)}")