from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from database import get_db, User, Enrollment, Course, UserCohort, CohortCourse, Cohort, Module, Session as SessionModel, Resource, SessionContent, PresenterCohort, Presenter, StudentSessionStatus, StudentModuleStatus
from resource_analytics_models import ResourceView
from assignment_quiz_models import Assignment, AssignmentSubmission, QuizResult, QuizStatus
from auth import get_current_user, get_current_user_any_role
from email_utils import send_course_enrollment_confirmation
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Student Dashboard"])

def get_student_enrollment_status(db: Session, student_id: int, course_id: int = None):
    """Helper function to get student enrollment status - ENROLLMENT + COHORT ACCESS REQUIRED"""
    from cohort_specific_models import CohortSpecificCourse, CohortSpecificEnrollment
    
    # Get direct enrollments for regular courses
    direct_enrollments = db.query(Enrollment).filter(
        Enrollment.student_id == student_id
    )
    if course_id:
        direct_enrollments = direct_enrollments.filter(Enrollment.course_id == course_id)
    direct_enrollments = direct_enrollments.all()
    
    # Get cohort-specific enrollments
    cohort_enrollments = db.query(CohortSpecificEnrollment).filter(
        CohortSpecificEnrollment.student_id == student_id
    )
    if course_id:
        cohort_enrollments = cohort_enrollments.filter(CohortSpecificEnrollment.course_id == course_id)
    cohort_enrollments = cohort_enrollments.all()
    
    # Get user's cohorts for access checking
    user_cohorts = db.query(UserCohort).filter(
        UserCohort.user_id == student_id,
        UserCohort.is_active == True
    ).all()
    
    # Get user object to check direct cohort_id
    user = db.query(User).filter(User.id == student_id).first()
    user_cohort_id = user.cohort_id if user else None
    
    # Get available cohort courses (for browse page)
    cohort_courses = []
    cohort_specific_courses = []
    cohort_assigned_course_ids = set()
    
    # Track which cohort IDs we've already processed
    processed_cohort_ids = set()
    
    # Combine cohort IDs from UserCohort and User table
    all_cohort_ids = [uc.cohort_id for uc in user_cohorts]
    if user_cohort_id and user_cohort_id not in all_cohort_ids:
        all_cohort_ids.append(user_cohort_id)
        
    for cid in all_cohort_ids:
        if cid in processed_cohort_ids:
            continue
        processed_cohort_ids.add(cid)
        
        # Get regular courses assigned to cohort from legacy table
        # Filter by approval_status
        cohort_course_assignments = db.query(CohortCourse).join(Course).filter(
            CohortCourse.cohort_id == cid,
            Course.approval_status == 'approved'
        ).all()
        cohort_courses.extend(cohort_course_assignments)
        
        # Get cohort-specific courses
        cohort_specific = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.cohort_id == cid,
            CohortSpecificCourse.is_active == True
        ).all()
        cohort_specific_courses.extend(cohort_specific)

    # 3. Add Courses from Unified CourseAssignment table (Comprehensive)
    from database import CourseAssignment
    from sqlalchemy import or_, and_
    
    ca_filters = [
        CourseAssignment.assignment_type == 'all',
        and_(CourseAssignment.assignment_type == 'individual', CourseAssignment.user_id == student_id)
    ]
    
    if user_cohort_id:
        ca_filters.append(and_(CourseAssignment.assignment_type == 'cohort', CourseAssignment.cohort_id == user_cohort_id))
    
    # Get any other cohorts the user is in
    additional_cohort_ids = [uc.cohort_id for uc in user_cohorts if uc.cohort_id != user_cohort_id]
    if additional_cohort_ids:
        ca_filters.append(and_(CourseAssignment.assignment_type == 'cohort', CourseAssignment.cohort_id.in_(additional_cohort_ids)))
    
    if user and hasattr(user, 'college') and user.college:
        ca_filters.append(and_(CourseAssignment.assignment_type == 'college', CourseAssignment.college == user.college))
    
    # Filter unified assignments by course approval status
    unified_assignments = db.query(CourseAssignment).join(Course).filter(
        Course.approval_status == 'approved',
        or_(*ca_filters)
    ).all()
    for ua in unified_assignments:
        cohort_assigned_course_ids.add(ua.course_id)
        
    # Also include legacy CohortCourse associations (already filtered by approval_status above)
    for cid in all_cohort_ids:
        cc_assignments = db.query(CohortCourse).join(Course).filter(
            CohortCourse.cohort_id == cid,
            Course.approval_status == 'approved'
        ).all()
        for cc in cc_assignments:
            cohort_assigned_course_ids.add(cc.course_id)
    
    # Combined sets for return
    enrolled_regular_course_ids = {e.course_id for e in direct_enrollments}
    enrolled_cohort_course_ids = {c.id for c in cohort_specific_courses}
    
    return {
        "direct_enrollments": direct_enrollments,
        "cohort_enrollments": cohort_enrollments,
        "user_cohorts": user_cohorts,
        "cohort_courses": cohort_courses,
        "cohort_specific_courses": cohort_specific_courses,
        "enrolled_regular_course_ids": enrolled_regular_course_ids,
        "enrolled_cohort_course_ids": enrolled_cohort_course_ids
    }

def calculate_course_progress(db: Session, student_id: int, course_id: int, course_type: str = "regular"):
    """
    Calculate overall progress for a course by aggregating progress of all its sessions hierarchically.
    Returns (progress_pct, total_resources, completed_resources, course_status, total_sessions, attended_sessions, total_modules)
    """
    try:
        if course_type == "cohort_specific":
            from cohort_specific_models import CohortCourseModule, CohortCourseSession
            modules = db.query(CohortCourseModule).order_by(CohortCourseModule.week_number).filter(CohortCourseModule.course_id == course_id).all()
        else:
            modules = db.query(Module).order_by(Module.week_number).filter(Module.course_id == course_id).all()
        
        if not modules:
            return 0, 0, 0, "Not Started", 0, 0, 0
            
        total_modules_progress = 0
        total_resources = 0
        completed_resources = 0
        total_sessions_count = 0
        attended_sessions_count = 0
        course_started = False
        all_completed = True
        
        for module in modules:
            if course_type == "cohort_specific":
                sessions = db.query(CohortCourseSession).order_by(CohortCourseSession.session_number).filter(CohortCourseSession.module_id == module.id).all()
                s_type = "cohort"
            else:
                sessions = db.query(SessionModel).order_by(SessionModel.session_number).filter(SessionModel.module_id == module.id).all()
                s_type = "global"
            
            if not sessions:
                continue
                
            module_session_progress_sum = 0
            for session in sessions:
                total_sessions_count += 1
                progress_pct, status, s_total, s_completed = calculate_student_session_progress(db, student_id, session.id, s_type)
                module_session_progress_sum += progress_pct
                total_resources += s_total
                completed_resources += s_completed
                
                if status == "Completed":
                    attended_sessions_count += 1
                
                if status != "Not Started":
                    course_started = True
                if status != "Completed":
                    all_completed = False
            
            module_progress = module_session_progress_sum / len(sessions)
            total_modules_progress += module_progress
            
        progress_pct = total_modules_progress / len(modules) if modules else 0
        
        # Determine course status
        if all_completed and total_resources > 0:
            status = "Completed"
        elif course_started or (modules and len(modules) > 0):
            status = "In Progress"
        else:
            status = "Not Started"
            
        return round(progress_pct), total_resources, completed_resources, status, total_sessions_count, attended_sessions_count, len(modules)
    except Exception as e:
        logger.error(f"Error calculating course progress: {str(e)}")
        return 0, 0, 0, "Not Started", 0, 0, 0

def calculate_student_session_progress(db: Session, student_id: int, session_id: int, session_type: str = "global"):
    """
    Calculate progress for a single session based on resource completion.
    Returns (completion_percentage, current_status, total_items, completed_items)
    """
    current_status = "Not Started"
    completion_percentage = 0
    total_items = 0
    completed_items = 0
    try:
        from resource_analytics_models import ResourceView
        
        # Get session status record
        status_record = db.query(StudentSessionStatus).filter(
            StudentSessionStatus.student_id == student_id,
            StudentSessionStatus.session_id == session_id,
            StudentSessionStatus.session_type == session_type
        ).first()
        
        if status_record:
            current_status = status_record.status
        
        # Get all resources for this session based on type
        if session_type == "cohort":
            from cohort_specific_models import CohortSessionContent, CohortCourseResource
            resources = db.query(CohortCourseResource).filter(
                CohortCourseResource.session_id == session_id
            ).all()
            session_contents = db.query(CohortSessionContent).filter(
                CohortSessionContent.session_id == session_id
            ).all()
        else:
            resources = db.query(Resource).filter(Resource.session_id == session_id).all()
            session_contents = db.query(SessionContent).filter(SessionContent.session_id == session_id).all()
        
        # Filter out meeting links from session contents for progress calculation
        trackable_session_contents = [c for c in session_contents if c.content_type != "MEETING_LINK"]
        
        total_items = len(resources) + len(trackable_session_contents)
        
        # Check for quizzes and assignments
        try:
            from assignment_quiz_tables import Quiz, QuizAttempt, QuizStatus, Assignment, AssignmentSubmission, AssignmentStatus
            quizzes = db.query(Quiz).filter(
                Quiz.session_id == session_id,
                Quiz.session_type == session_type
            ).all()
            total_items += len(quizzes)
            
            assignments = db.query(Assignment).filter(
                Assignment.session_id == session_id,
                Assignment.session_type == session_type
            ).all()
            total_items += len(assignments)
        except ImportError:
            quizzes = []
            assignments = []
            
        if total_items == 0:
            # If "Started" manually but no resources, keep it Started
            return 0, current_status, 0, 0
            
        completed_items = 0
        
        # Check resources
        for resource in resources:
            view = db.query(ResourceView).filter(
                ResourceView.student_id == student_id,
                ResourceView.resource_id == resource.id,
                ResourceView.resource_type == ("COHORT_RESOURCE" if session_type == "cohort" else "RESOURCE")
            ).first()
            if view:
                completed_items += 1
                
        # Check session contents (already filtered trackable ones)
        for content in trackable_session_contents:
            if content.content_type in ["MATERIAL", "RESOURCE", "VIDEO"]:
                view = db.query(ResourceView).filter(
                    ResourceView.student_id == student_id,
                    ResourceView.resource_id == content.id,
                    ResourceView.resource_type == ("COHORT_RESOURCE" if session_type == "cohort" else "RESOURCE")
                ).first()
                if view:
                    completed_items += 1
            else:
                # Other trackable types
                if current_status != "Not Started" and current_status != "Staff View":
                    completed_items += 1
                    
        # Check quizzes
        for quiz in quizzes:
            attempt = db.query(QuizAttempt).filter(
                QuizAttempt.quiz_id == quiz.id,
                QuizAttempt.student_id == student_id,
                QuizAttempt.status == QuizStatus.COMPLETED
            ).first()
            if attempt:
                completed_items += 1
        
        # Check assignments
        for assignment in assignments:
            submission = db.query(AssignmentSubmission).filter(
                AssignmentSubmission.assignment_id == assignment.id,
                AssignmentSubmission.student_id == student_id,
                AssignmentSubmission.status.in_([AssignmentStatus.SUBMITTED, AssignmentStatus.EVALUATED])
            ).first()
            if submission:
                completed_items += 1
                
        completion_percentage = (completed_items / total_items) * 100
        
        # Session is "Started" if any resource is visible (handled by being at this point)
        # and specially if any item is completed
        if completion_percentage >= 99.9: # Use threshold for floats
            target_status = "Completed"
        elif completion_percentage > 0 or current_status == "Started":
            target_status = "Started"
        else:
            target_status = "Not Started"

        # Update status record if changed
        if not status_record and target_status != "Not Started":
            status_record = StudentSessionStatus(
                student_id=student_id,
                session_id=session_id,
                session_type=session_type,
                status=target_status,
                started_at=datetime.utcnow() if target_status == "Started" else None,
                completed_at=datetime.utcnow() if target_status == "Completed" else None,
                progress_percentage=completion_percentage
            )
            db.add(status_record)
            db.commit()
        elif status_record:
            should_commit = False
            if status_record.status != target_status:
                status_record.status = target_status
                if target_status == "Completed" and not status_record.completed_at:
                    status_record.completed_at = datetime.utcnow()
                should_commit = True
            
            if abs((status_record.progress_percentage or 0) - completion_percentage) > 0.1:
                status_record.progress_percentage = completion_percentage
                should_commit = True
            
            if should_commit:
                db.commit()
            
        return round(completion_percentage), target_status, total_items, completed_items
    except Exception as e:
        logger.error(f"Calculate progress error: {str(e)}")
        return round(completion_percentage), current_status, total_items, completed_items
    except Exception as e:
        logger.error(f"Calculate progress error: {str(e)}")
        return round(completion_percentage), current_status



@router.post("/student/session/{session_id}/start")
async def start_student_session(
    session_id: int,
    session_type: str = "global",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a session as started - supports both global and cohort sessions"""
    try:
        status_record = db.query(StudentSessionStatus).filter(
            StudentSessionStatus.student_id == current_user.id,
            StudentSessionStatus.session_id == session_id,
            StudentSessionStatus.session_type == session_type
        ).first()
        
        if not status_record:
            status_record = StudentSessionStatus(
                student_id=current_user.id,
                session_id=session_id,
                session_type=session_type,
                status="Started",
                started_at=datetime.utcnow()
            )
            db.add(status_record)
            db.commit()
            
            # Also ensure Module is started
            if session_type == "cohort":
                from cohort_specific_models import CohortCourseSession
                session = db.query(CohortCourseSession).filter(
                    CohortCourseSession.id == session_id
                ).first()
            else:
                session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            
            if session:
                module_status = db.query(StudentModuleStatus).filter(
                    StudentModuleStatus.student_id == current_user.id,
                    StudentModuleStatus.module_id == session.module_id,
                    StudentModuleStatus.module_type == session_type
                ).first()
                
                if not module_status:
                    module_status = StudentModuleStatus(
                        student_id=current_user.id,
                        module_id=session.module_id,
                        module_type=session_type,
                        status="Started",
                        started_at=datetime.utcnow()
                    )
                    db.add(module_status)
                    db.commit()
                    
        return {"status": "Started", "message": "Session marked as started"}
    except Exception as e:
        logger.error(f"Start session error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")

from schemas import UserUpdate

@router.post("/student/module/{module_id}/start")
async def start_student_module(
    module_id: int,
    module_type: str = "global",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a module as started - supports both global and cohort modules"""
    try:
        status_record = db.query(StudentModuleStatus).filter(
            StudentModuleStatus.student_id == current_user.id,
            StudentModuleStatus.module_id == module_id,
            StudentModuleStatus.module_type == module_type
        ).first()
        
        if not status_record:
            status_record = StudentModuleStatus(
                student_id=current_user.id,
                module_id=module_id,
                module_type=module_type,
                status="Started",
                started_at=datetime.utcnow()
            )
            db.add(status_record)
            db.commit()
        
        return {"status": "Started", "message": "Module marked as started"}
    except Exception as e:
        logger.error(f"Start module error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/student/profile")
async def update_student_profile(
    profile_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update student's own profile"""
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        update_data = profile_data.dict(exclude_unset=True)
        # Students shouldn't be able to change certain things here if we want to be strict,
        # but for now we'll allow username, email, and github_link.
        
        # Prevent email duplication
        if 'email' in update_data and update_data['email'] != user.email:
            if db.query(User).filter(User.email == update_data['email']).first():
                raise HTTPException(status_code=400, detail="Email already exists")
        
        for field, value in update_data.items():
            if field in ["username", "email", "github_link", "password", "college", "department", "year"]:
                if field == "password":
                    from auth import get_password_hash
                    user.password_hash = get_password_hash(value)
                else:
                    setattr(user, field, value)
        
        db.commit()
        return {"message": "Profile updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update student profile error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update profile")

@router.get("/student/my-cohort")
async def get_student_my_cohort(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the authenticated student's assigned cohort"""
    try:
        # Get user's active cohorts
        user_cohorts = db.query(UserCohort).filter(
            UserCohort.user_id == current_user.id,
            UserCohort.is_active == True
        ).all()
        
        if not user_cohorts:
            return {
                "cohort": None,
                "message": "No active cohort assigned"
            }
        
        # Get the first active cohort (assuming a student is in one cohort)
        cohort = db.query(Cohort).filter(
            Cohort.id == user_cohorts[0].cohort_id,
            Cohort.is_active == True
        ).first()
        
        if not cohort:
            return {
                "cohort": None,
                "message": "Cohort not found or inactive"
            }
        
        # Get presenter assigned to this cohort
        presenter_cohort = db.query(PresenterCohort).filter(
            PresenterCohort.cohort_id == cohort.id
        ).first()
        
        instructor_name = "Admin"  # Default fallback
        if presenter_cohort:
            presenter = db.query(Presenter).filter(
                Presenter.id == presenter_cohort.presenter_id
            ).first()
            if presenter:
                instructor_name = presenter.username
        
        # Get user count
        user_count = db.query(UserCohort).filter(
            UserCohort.cohort_id == cohort.id,
            UserCohort.is_active == True
        ).count()
        
        return {
            "cohort": {
                "id": cohort.id,
                "name": cohort.name,
                "description": cohort.description or "",
                "is_active": cohort.is_active,
                "user_count": user_count,
                "instructor_name": instructor_name,
                "start_date": cohort.start_date.isoformat() if cohort.start_date else None,
                "end_date": cohort.end_date.isoformat() if cohort.end_date else None
            }
        }
        
    except Exception as e:
        logger.error(f"Get student cohort error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch cohort information")


@router.get("/student/dashboard")
async def get_student_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get student dashboard data including enrolled courses"""
    try:
        # Check if student has filled GitHub Link - Requirement
        if current_user.role == "Student" and not current_user.github_link:
            return {
                "redirect_to_profile": True,
                "message": "Please update your GitHub Link in profile to access dashboard"
            }

        # Get student's enrollment status using helper function
        enrollment_status = get_student_enrollment_status(db, current_user.id)
        direct_enrollments = enrollment_status["direct_enrollments"]
        cohort_enrollments = enrollment_status["cohort_enrollments"]
        user_cohorts = enrollment_status["user_cohorts"]
        cohort_courses = enrollment_status["cohort_courses"]
        cohort_specific_courses = enrollment_status["cohort_specific_courses"]
        enrolled_regular_course_ids = enrollment_status["enrolled_regular_course_ids"]
        enrolled_cohort_course_ids = enrollment_status["enrolled_cohort_course_ids"]
        
        # Create direct enrolled course IDs set from direct enrollments
        direct_enrolled_course_ids = {e.course_id for e in direct_enrollments}
        
        cohort_info = None
        if user_cohorts:
            cohort = db.query(Cohort).filter(Cohort.id == user_cohorts[0].cohort_id).first()
            if cohort:
                # Get presenter assigned to this cohort
                presenter_cohort = db.query(PresenterCohort).filter(PresenterCohort.cohort_id == cohort.id).first()
                instructor_name = "Admin"  # Default fallback
                if presenter_cohort:
                    presenter = db.query(Presenter).filter(Presenter.id == presenter_cohort.presenter_id).first()
                    if presenter:
                        instructor_name = presenter.username
                
                cohort_info = {
                    "id": cohort.id,
                    "name": cohort.name,
                    "instructor_name": instructor_name,
                    "total_users": db.query(UserCohort).filter(UserCohort.cohort_id == cohort.id).count(),
                    "total_courses": db.query(CohortCourse).filter(CohortCourse.cohort_id == cohort.id).count()
                }
        
        # Get course details - include both regular and cohort-specific courses
        enrolled_courses = []
        upcoming_sessions = []
        recent_assignments = []
        
        # Process regular courses assigned to cohort - only if enrolled
        if enrolled_regular_course_ids:
            courses = db.query(Course).filter(Course.id.in_(enrolled_regular_course_ids)).all()
            current_time = datetime.now()
            
            for course in courses:
                # Find the enrollment record for progress (direct enrollment only)
                enrollment = next((e for e in direct_enrollments if e.course_id == course.id), None)
                progress = enrollment.progress if enrollment else 0
                is_directly_enrolled = course.id in direct_enrolled_course_ids
                
                # Get modules and sessions for this course
                modules = db.query(Module).filter(Module.course_id == course.id).all()
                total_sessions = 0
                next_session = None
                
                for module in modules:
                    sessions = db.query(SessionModel).filter(SessionModel.module_id == module.id).all()
                    total_sessions += len(sessions)
                    
                    # Find next upcoming session
                    for session in sessions:
                        if session.scheduled_time and session.scheduled_time > current_time:
                            if not next_session or (next_session.get("scheduled_time") and session.scheduled_time < next_session["scheduled_time"]):
                                next_session = {
                                    "id": session.id,
                                    "title": session.title,
                                    "scheduled_time": session.scheduled_time
                                }
                            
                            upcoming_sessions.append({
                                "id": session.id,
                                "title": session.title,
                                "course_title": course.title,
                                "scheduled_date": session.scheduled_time.strftime("%Y-%m-%d") if session.scheduled_time else None,
                                "scheduled_time": session.scheduled_time.strftime("%H:%M") if session.scheduled_time else None,
                                "scheduled_datetime": session.scheduled_time,
                                "duration_minutes": session.duration_minutes,
                                "zoom_link": session.zoom_link
                            })
                        elif not session.scheduled_time and not next_session:
                            next_session = {
                                "id": session.id,
                                "title": session.title,
                                "scheduled_time": None,
                                "status": "unscheduled"
                            }
                
                progress_pct, total_res, completed_res, course_status, total_sessions_count, attended_sessions_count, total_modules_count = calculate_course_progress(db, current_user.id, course.id, "regular")
                
                # Fetch enrollment record safely for payment info
                enrollment_obj = db.query(Enrollment).filter(Enrollment.student_id == current_user.id, Enrollment.course_id == course.id).first()
                
                # Determine accurate payment status if no enrollment record exists
                payment_status = 'not_required'
                if enrollment_obj:
                    payment_status = enrollment_obj.payment_status
                else:
                    # Check if it should be paid based on course or assignment
                    is_paid = course.payment_type == 'paid'
                    # Also check assignments
                    from database import CourseAssignment
                    assignment = db.query(CourseAssignment).filter(
                        CourseAssignment.course_id == course.id,
                        or_(
                            CourseAssignment.assignment_type == 'all',
                            and_(CourseAssignment.assignment_type == 'individual', CourseAssignment.user_id == current_user.id),
                            and_(CourseAssignment.assignment_type == 'cohort', CourseAssignment.cohort_id.in_([uc.cohort_id for uc in user_cohorts or []]))
                        )
                    ).first()
                    if assignment and assignment.assignment_mode == 'paid':
                        is_paid = True
                    
                    if is_paid:
                        payment_status = 'pending_payment'

                enrolled_courses.append({
                    "id": course.id,
                    "title": course.title,
                    "description": course.description,
                    "duration_weeks": course.duration_weeks,
                    "sessions_per_week": course.sessions_per_week,
                    "is_active": course.is_active,
                    "banner_image": course.banner_image,
                    "progress": progress_pct,
                    "total_resources": total_res,
                    "completed_resources": completed_res,
                    "status": course_status,
                    "total_sessions": total_sessions_count,
                    "attended_sessions": attended_sessions_count,
                    "total_modules": total_modules_count,
                    "next_session": next_session,
                    "created_at": course.created_at,
                    "is_directly_enrolled": is_directly_enrolled,
                    "access_type": "cohort_assigned",
                    "course_type": "regular",
                    "payment_status": payment_status,
                    "payment_amount": enrollment_obj.payment_amount if enrollment_obj else (assignment.amount if (assignment and assignment.assignment_mode == 'paid') else course.default_price)
                })
        
        # Process cohort-specific courses - only if enrolled
        enrolled_cohort_courses = []
        if enrolled_cohort_course_ids:
            enrolled_cohort_courses = [c for c in cohort_specific_courses if c.id in enrolled_cohort_course_ids]
        
        if enrolled_cohort_courses:
            from cohort_specific_models import CohortCourseModule, CohortCourseSession
            
            for cohort_course in enrolled_cohort_courses:
                # Get modules and sessions for cohort-specific course
                modules = db.query(CohortCourseModule).filter(CohortCourseModule.course_id == cohort_course.id).all()
                total_sessions = 0
                next_session = None
                current_time = datetime.now()
                
                # Find enrollment for progress
                enrollment = next((e for e in cohort_enrollments if e.course_id == cohort_course.id), None)
                progress = enrollment.progress if enrollment else 0
                
                for module in modules:
                    sessions = db.query(CohortCourseSession).filter(CohortCourseSession.module_id == module.id).all()
                    total_sessions += len(sessions)
                    
                    # Find next upcoming session
                    for session in sessions:
                        if session.scheduled_time and session.scheduled_time > current_time:
                            if not next_session or (next_session.get("scheduled_time") and session.scheduled_time < next_session["scheduled_time"]):
                                next_session = {
                                    "id": session.id,
                                    "title": session.title,
                                    "scheduled_time": session.scheduled_time
                                }
                            
                            upcoming_sessions.append({
                                "id": session.id,
                                "title": session.title,
                                "course_title": cohort_course.title,
                                "scheduled_date": session.scheduled_time.strftime("%Y-%m-%d") if session.scheduled_time else None,
                                "scheduled_time": session.scheduled_time.strftime("%H:%M") if session.scheduled_time else None,
                                "scheduled_datetime": session.scheduled_time,
                                "duration_minutes": session.duration_minutes,
                                "zoom_link": session.zoom_link
                            })
                        elif not session.scheduled_time and not next_session:
                            next_session = {
                                "id": session.id,
                                "title": session.title,
                                "scheduled_time": None,
                                "status": "unscheduled"
                            }
                
                progress_pct, total_res, completed_res, course_status, total_sessions_count, attended_sessions_count, total_modules_count = calculate_course_progress(db, current_user.id, cohort_course.id, "cohort_specific")

                enrolled_courses.append({
                    "id": cohort_course.id,
                    "title": cohort_course.title,
                    "description": cohort_course.description,
                    "duration_weeks": cohort_course.duration_weeks,
                    "sessions_per_week": cohort_course.sessions_per_week,
                    "is_active": cohort_course.is_active,
                    "banner_image": cohort_course.banner_image,
                    "progress": progress_pct,
                    "total_resources": total_res,
                    "completed_resources": completed_res,
                    "status": course_status,
                    "total_sessions": total_sessions_count,
                    "attended_sessions": attended_sessions_count,
                    "total_modules": total_modules_count,
                    "next_session": next_session,
                    "created_at": cohort_course.created_at,
                    "is_directly_enrolled": True,
                    "access_type": "cohort_specific",
                    "course_type": "cohort_specific"
                })
        
        # Get assignments for all courses (regular and cohort-specific)
        if enrolled_regular_course_ids:
            courses = db.query(Course).filter(Course.id.in_(enrolled_regular_course_ids)).all()
            for course in courses:
                modules = db.query(Module).filter(Module.course_id == course.id).all()
                for module in modules:
                    sessions = db.query(SessionModel).filter(SessionModel.module_id == module.id).all()
                    for session in sessions:
                        assignments = db.query(Assignment).filter(
                            Assignment.session_id == session.id, 
                            Assignment.session_type == "global",
                            Assignment.is_active == True
                        ).all()
                        for assignment in assignments:
                            submission = db.query(AssignmentSubmission).filter(
                                AssignmentSubmission.assignment_id == assignment.id,
                                AssignmentSubmission.student_id == current_user.id
                            ).first()
                            
                            grade = None
                            if submission:
                                from assignment_quiz_models import AssignmentGrade
                                grade_record = db.query(AssignmentGrade).filter(
                                    AssignmentGrade.submission_id == submission.id
                                ).first()
                                if grade_record:
                                    grade = {
                                        "marks_obtained": grade_record.marks_obtained,
                                        "total_marks": grade_record.total_marks,
                                        "percentage": grade_record.percentage
                                    }
                            
                            recent_assignments.append({
                                "id": assignment.id,
                                "title": assignment.title,
                                "course_title": course.title,
                                "due_date": assignment.due_date,
                                "total_marks": assignment.total_marks,
                                "submitted": submission is not None,
                                "submission_id": submission.id if submission else None,
                                "score": grade["percentage"] if grade else None,
                                "marks_obtained": grade["marks_obtained"] if grade else None
                            })
        
        # Get assignments for cohort-specific courses
        if enrolled_cohort_course_ids:
            from cohort_specific_models import CohortSpecificCourse, CohortCourseModule, CohortCourseSession
            
            cohort_courses = db.query(CohortSpecificCourse).filter(
                CohortSpecificCourse.id.in_(enrolled_cohort_course_ids)
            ).all()
            
            for course in cohort_courses:
                modules = db.query(CohortCourseModule).filter(
                    CohortCourseModule.course_id == course.id
                ).all()
                for module in modules:
                    sessions = db.query(CohortCourseSession).filter(
                        CohortCourseSession.module_id == module.id
                    ).all()
                    for session in sessions:
                        assignments = db.query(Assignment).filter(
                            Assignment.session_id == session.id,
                            Assignment.session_type == "cohort",
                            Assignment.is_active == True
                        ).all()
                        for assignment in assignments:
                            submission = db.query(AssignmentSubmission).filter(
                                AssignmentSubmission.assignment_id == assignment.id,
                                AssignmentSubmission.student_id == current_user.id
                            ).first()
                            
                            grade = None
                            if submission:
                                from assignment_quiz_models import AssignmentGrade
                                grade_record = db.query(AssignmentGrade).filter(
                                    AssignmentGrade.submission_id == submission.id
                                ).first()
                                if grade_record:
                                    grade = {
                                        "marks_obtained": grade_record.marks_obtained,
                                        "total_marks": grade_record.total_marks,
                                        "percentage": grade_record.percentage
                                    }
                            
                            recent_assignments.append({
                                "id": assignment.id,
                                "title": assignment.title,
                                "course_title": course.title,
                                "due_date": assignment.due_date,
                                "total_marks": assignment.total_marks,
                                "submitted": submission is not None,
                                "submission_id": submission.id if submission else None,
                                "score": grade["percentage"] if grade else None,
                                "marks_obtained": grade["marks_obtained"] if grade else None
                            })
        
        # Sort assignments by due date
        recent_assignments.sort(key=lambda x: x["due_date"])
        
        # Sort upcoming sessions by datetime
        upcoming_sessions.sort(key=lambda x: (x["scheduled_datetime"] is None, x["scheduled_datetime"]))
        
        total_all_resources = sum(c.get("total_resources", 0) for c in enrolled_courses)
        completed_all_resources = sum(c.get("completed_resources", 0) for c in enrolled_courses)
        
        progress_summary = {
            "completed_courses": len([c for c in enrolled_courses if c["progress"] >= 100]),
            "average_progress": round(sum(c["progress"] for c in enrolled_courses) / len(enrolled_courses), 1) if enrolled_courses else 0,
            "total_resources": total_all_resources,
            "completed_resources": completed_all_resources
        }
        
        return {
            "enrolled_courses": enrolled_courses,
            "upcoming_sessions": upcoming_sessions[:10],  # Limit to 10
            "recent_assignments": recent_assignments,
            "progress_summary": progress_summary,
            "cohort_info": cohort_info,
            "total_courses": len(enrolled_courses),
            "user_info": {
                "id": current_user.id,
                "username": current_user.username,
                "email": current_user.email,
                "college": current_user.college,
                "department": current_user.department,
                "year": current_user.year
            }
        }
    except Exception as e:
        logger.error(f"Student dashboard error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard data")

@router.get("/student/courses")
async def get_student_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all courses - cohort-assigned and cohort-specific are available, others are locked"""
    try:
        from cohort_specific_models import CohortSpecificCourse
        
        # Get student's cohorts for context
        user_cohorts = db.query(UserCohort).filter(
            UserCohort.user_id == current_user.id,
            UserCohort.is_active == True
        ).all()
        
        cohort_info = None
        if user_cohorts:
            cohort = db.query(Cohort).filter(Cohort.id == user_cohorts[0].cohort_id).first()
            if cohort:
                presenter_cohort = db.query(PresenterCohort).filter(PresenterCohort.cohort_id == cohort.id).first()
                instructor_name = "Admin"
                if presenter_cohort:
                    presenter = db.query(Presenter).filter(Presenter.id == presenter_cohort.presenter_id).first()
                    if presenter:
                        instructor_name = presenter.username
                
                cohort_info = {
                    "id": cohort.id,
                    "name": cohort.name,
                    "instructor_name": instructor_name
                }
        
        # Get student's enrollment status
        enrollment_status = get_student_enrollment_status(db, current_user.id)
        enrolled_regular_course_ids = enrollment_status["enrolled_regular_course_ids"]

        # Get all active and approved regular courses
        all_courses = db.query(Course).filter(
            Course.is_active == True,
            Course.approval_status == 'approved'
        ).all()

        # Get all course assignments
        from database import CourseAssignment
        assignments = db.query(CourseAssignment).all()
        
        # Course ID -> is_assigned mapping
        assigned_courses = set()
        for assignment in assignments:
            if assignment.assignment_type == 'all':
                assigned_courses.add(assignment.course_id)
            elif assignment.assignment_type == 'individual' and assignment.user_id == current_user.id:
                assigned_courses.add(assignment.course_id)
            elif assignment.assignment_type == 'college' and assignment.college == current_user.college:
                assigned_courses.add(assignment.course_id)
            elif assignment.assignment_type == 'cohort':
                user_cohort_ids = [uc.cohort_id for uc in user_cohorts]
                if assignment.cohort_id in user_cohort_ids:
                    assigned_courses.add(assignment.course_id)
        
        courses = []
        
        # Process regular courses (ONLY SHOW IF ASSIGNED)
        for course in all_courses:
            # Check if this course is assigned to the user
            if course.id not in assigned_courses:
                continue

            is_enrolled = course.id in enrolled_regular_course_ids
            is_locked = not is_enrolled # It is joinable if assigned, but locked until enrolled? No, usually "locked" means "cannot enroll". 
            # If it's assigned, they can enroll.
            
            # Find specific assignment for this course to get mode/amount
            assignment_info = db.query(CourseAssignment).filter(
                CourseAssignment.course_id == course.id,
                or_(
                    CourseAssignment.assignment_type == 'all',
                    and_(CourseAssignment.assignment_type == 'individual', CourseAssignment.user_id == current_user.id),
                    and_(CourseAssignment.assignment_type == 'college', CourseAssignment.college == current_user.college),
                    and_(CourseAssignment.assignment_type == 'cohort', CourseAssignment.cohort_id.in_([uc.cohort_id for uc in user_cohorts]))
                )
            ).first()

            assignment_mode = assignment_info.assignment_mode if assignment_info else 'free'
            amount = assignment_info.amount if assignment_info else 0.0

            # Fetch enrollment record safely for payment info
            enrollment_rec = db.query(Enrollment).filter(Enrollment.student_id == current_user.id, Enrollment.course_id == course.id).first()

            # Determine accurate payment status if no enrollment record exists
            payment_status = 'not_required'
            enrolled = False
            if enrollment_rec:
                payment_status = enrollment_rec.payment_status
                # If they have an enrollment record and status is paid/not_required, they are "enrolled"
                if payment_status in ['paid', 'not_required']:
                    enrolled = True
            else:
                if assignment_mode == 'paid' or course.payment_type == 'paid':
                    payment_status = 'pending_payment'

            courses.append({
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "duration_weeks": course.duration_weeks,
                "sessions_per_week": course.sessions_per_week,
                "is_active": course.is_active,
                "banner_image": course.banner_image,
                "enrolled": enrolled,
                "is_cohort_assigned": True, 
                "is_locked": not enrolled and payment_status == 'pending_payment',
                "lock_reason": "This is a premium course requiring enrollment fee." if (not enrolled and payment_status == 'pending_payment') else None,
                "access_level": "enrolled" if enrolled else "available",
                "created_at": course.created_at,
                "course_type": "regular",
                "payment_type": course.payment_type,
                "default_price": course.default_price,
                "assignment_mode": assignment_mode,
                "amount": amount,
                "payment_status": payment_status,
                "price": amount if assignment_mode == 'paid' else (course.default_price if course.payment_type == 'paid' else 0),
                "modules_count": db.query(Module).filter(Module.course_id == course.id).count(),
                "total_sessions": db.query(SessionModel).join(Module).filter(Module.course_id == course.id).count()
            })
        
        # Cohort courses are not shown in Browse page per requirement
        # Only global courses that are assigned to the user are shown above
        
        return {
            "courses": courses,
            "total": len(courses),
            "user_cohort": cohort_info
        }
    except Exception as e:
        logger.error(f"Get student courses error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch courses")

@router.post("/student/enroll/{course_id}")
async def enroll_in_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Enroll student in a course - requires cohort access"""
    try:
        from cohort_specific_models import CohortSpecificCourse, CohortSpecificEnrollment
        
        # Check if it's a regular course or cohort-specific course
        regular_course = db.query(Course).filter(Course.id == course_id).first()
        cohort_course = db.query(CohortSpecificCourse).filter(CohortSpecificCourse.id == course_id).first()
        
        if not regular_course and not cohort_course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        course = regular_course or cohort_course
        
        # Check if course is active and approved
        if not course.is_active:
            raise HTTPException(status_code=400, detail="Course is not active")
        
        if course.approval_status != 'approved':
            raise HTTPException(status_code=403, detail="Course is pending approval and not available for enrollment")
        
        # Get user's cohorts
        user_cohorts = db.query(UserCohort).filter(
            UserCohort.user_id == current_user.id,
            UserCohort.is_active == True
        ).all()
        
        if not user_cohorts:
            raise HTTPException(status_code=403, detail="You must be assigned to a cohort to enroll in courses.")
        
        # Check access permissions (Unified access check)
        from database import CourseAssignment
        has_access = False
        
        if regular_course:
            # Check legacy CohortCourse assignment
            for uc in user_cohorts:
                cohort_course_assignment = db.query(CohortCourse).filter(
                    CohortCourse.cohort_id == uc.cohort_id,
                    CohortCourse.course_id == course_id
                ).first()
                if cohort_course_assignment:
                    has_access = True
                    break
            
            # Check unified CourseAssignment (Comprehensive)
            if not has_access:
                user = db.query(User).filter(User.id == current_user.id).first()
                ca_filters = [
                    CourseAssignment.course_id == course_id,
                    or_(
                        CourseAssignment.assignment_type == 'all',
                        and_(CourseAssignment.assignment_type == 'individual', CourseAssignment.user_id == current_user.id),
                        and_(CourseAssignment.assignment_type == 'cohort', CourseAssignment.cohort_id.in_([uc.cohort_id for uc in user_cohorts])),
                        and_(CourseAssignment.assignment_type == 'college', CourseAssignment.college == (user.college if user else None))
                    )
                ]
                assignment = db.query(CourseAssignment).filter(*ca_filters).first()
                if assignment:
                    has_access = True
        else:
            # Check if cohort-specific course belongs to user's cohort
            for uc in user_cohorts:
                if cohort_course.cohort_id == uc.cohort_id:
                    has_access = True
                    break
        
        if not has_access:
            raise HTTPException(status_code=403, detail="This course is not available for enrollment. Please contact your coordinator.")
        
        if regular_course:
            # Check if already enrolled in regular course
            existing_enrollment = db.query(Enrollment).filter(
                Enrollment.student_id == current_user.id,
                Enrollment.course_id == course_id
            ).first()
            
            if existing_enrollment:
                raise HTTPException(status_code=400, detail="Already enrolled in this course")
            
            # Determine payment status and amount based on assignment or course default
            assignment_info = db.query(CourseAssignment).filter(
                CourseAssignment.course_id == course_id,
                or_(
                    CourseAssignment.assignment_type == 'all',
                    and_(CourseAssignment.assignment_type == 'individual', CourseAssignment.user_id == current_user.id),
                    and_(CourseAssignment.assignment_type == 'college', CourseAssignment.college == current_user.college),
                    and_(CourseAssignment.assignment_type == 'cohort', CourseAssignment.cohort_id.in_([uc.cohort_id for uc in user_cohorts]))
                )
            ).first()

            payment_mode = assignment_info.assignment_mode if assignment_info else regular_course.payment_type
            payment_amount = assignment_info.amount if (assignment_info and assignment_info.assignment_mode == 'paid') else regular_course.default_price
            
            # For simulation, if they call this endpoint, we assume they "paid" if it was required
            payment_status = 'paid' if payment_mode == 'paid' else 'not_required'

            # Create enrollment record for regular course
            enrollment = Enrollment(
                student_id=current_user.id,
                course_id=course_id,
                progress=0,
                payment_status=payment_status,
                payment_amount=payment_amount if payment_status == 'paid' else 0.0
            )
            db.add(enrollment)
            db.commit()
            db.refresh(enrollment)
            
            # Send enrollment confirmation email
            await send_course_enrollment_confirmation(
                db=db,
                user_id=current_user.id,
                course_title=course.title,
                course_description=course.description or "",
                duration_weeks=course.duration_weeks or 0,
                sessions_per_week=course.sessions_per_week or 0,
                course_start_date="TBD"  # You can calculate this based on course schedule
            )
            
            return {
                "message": "Successfully enrolled in course",
                "enrollment_id": enrollment.id,
                "course_title": course.title,
                "course_type": "regular"
            }
        else:
            # Check if already enrolled in cohort-specific course
            existing_enrollment = db.query(CohortSpecificEnrollment).filter(
                CohortSpecificEnrollment.student_id == current_user.id,
                CohortSpecificEnrollment.course_id == course_id
            ).first()
            
            if existing_enrollment:
                raise HTTPException(status_code=400, detail="Already enrolled in this course")
            
            # Create enrollment record for cohort-specific course
            enrollment = CohortSpecificEnrollment(
                student_id=current_user.id,
                course_id=course_id,
                progress=0
            )
            db.add(enrollment)
            db.commit()
            db.refresh(enrollment)
            
            # Send enrollment confirmation email
            await send_course_enrollment_confirmation(
                db=db,
                user_id=current_user.id,
                course_title=course.title,
                course_description=course.description or "",
                duration_weeks=course.duration_weeks or 0,
                sessions_per_week=course.sessions_per_week or 0,
                course_start_date="TBD"  # You can calculate this based on course schedule
            )
            
            return {
                "message": "Successfully enrolled in cohort-specific course",
                "enrollment_id": enrollment.id,
                "course_title": course.title,
                "course_type": "cohort_specific"
            }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Enrollment error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to enroll in course")

@router.get("/student/enrolled-courses")
async def get_enrolled_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get student's enrolled courses - only explicitly enrolled courses"""
    try:
        from cohort_specific_models import CohortSpecificCourse
        
        # Get student's enrollment status using helper function
        enrollment_status = get_student_enrollment_status(db, current_user.id)
        direct_enrollments = enrollment_status["direct_enrollments"]
        cohort_enrollments = enrollment_status["cohort_enrollments"]
        enrolled_regular_course_ids = enrollment_status["enrolled_regular_course_ids"]
        enrolled_cohort_course_ids = enrollment_status["enrolled_cohort_course_ids"]
        
        enrolled_courses = []
        
        # Get regular courses that student has explicitly enrolled in
        if enrolled_regular_course_ids:
            courses = db.query(Course).filter(Course.id.in_(enrolled_regular_course_ids)).all()
            
            for course in courses:
                progress_pct, total_res, completed_res, course_status, total_sessions_count, attended_sessions_count, total_modules_count = calculate_course_progress(db, current_user.id, course.id, "regular")
                
                # Fetch enrollment record safely for payment info
                enrollment_obj = db.query(Enrollment).filter(Enrollment.student_id == current_user.id, Enrollment.course_id == course.id).first()
                
                # Determine accurate payment status if no enrollment record exists
                payment_status = 'not_required'
                if enrollment_obj:
                    payment_status = enrollment_obj.payment_status
                else:
                    # Check if it should be paid based on course or assignment
                    is_paid = course.payment_type == 'paid'
                    # Also check assignments
                    from database import CourseAssignment
                    assignment = db.query(CourseAssignment).filter(
                        CourseAssignment.course_id == course.id,
                        or_(
                            CourseAssignment.assignment_type == 'all',
                            and_(CourseAssignment.assignment_type == 'individual', CourseAssignment.user_id == current_user.id),
                            and_(CourseAssignment.assignment_type == 'cohort', CourseAssignment.cohort_id.in_([uc.cohort_id for uc in enrollment_status["user_cohorts"]]))
                        )
                    ).first()
                    if assignment and assignment.assignment_mode == 'paid':
                        is_paid = True
                    
                    if is_paid:
                        payment_status = 'pending_payment'

                enrolled_courses.append({
                    "id": course.id,
                    "title": course.title,
                    "description": course.description,
                    "duration_weeks": course.duration_weeks,
                    "sessions_per_week": course.sessions_per_week,
                    "is_active": course.is_active,
                    "banner_image": course.banner_image,
                    "progress": progress_pct,
                    "total_resources": total_res,
                    "completed_resources": completed_res,
                    "total_sessions": total_sessions_count,
                    "attended_sessions": attended_sessions_count,
                    "total_modules": total_modules_count,
                    "status": course_status,
                    "created_at": course.created_at,
                    "course_type": "regular",
                    "payment_status": payment_status,
                    "payment_amount": enrollment_obj.payment_amount if enrollment_obj else (assignment.amount if (assignment and assignment.assignment_mode == 'paid') else course.default_price)
                })
        
        # Get all active cohort-specific courses for the user's cohort(s)
        # These are automatically "enrolled" / visible in My Courses
        user_cohort_ids = [uc.cohort_id for uc in enrollment_status["user_cohorts"]]
        
        if user_cohort_ids:
            cohort_courses = db.query(CohortSpecificCourse).filter(
                CohortSpecificCourse.cohort_id.in_(user_cohort_ids),
                CohortSpecificCourse.is_active == True
            ).all()
            
            for cohort_course in cohort_courses:
                progress_pct, total_res, completed_res, course_status, total_sessions_count, attended_sessions_count, total_modules_count = calculate_course_progress(db, current_user.id, cohort_course.id, "cohort_specific")
                
                enrolled_courses.append({
                    "id": cohort_course.id,
                    "title": cohort_course.title,
                    "description": cohort_course.description,
                    "duration_weeks": cohort_course.duration_weeks,
                    "sessions_per_week": cohort_course.sessions_per_week,
                    "is_active": cohort_course.is_active,
                    "banner_image": cohort_course.banner_image,
                    "progress": progress_pct,
                    "total_resources": total_res,
                    "completed_resources": completed_res,
                    "total_sessions": total_sessions_count,
                    "attended_sessions": attended_sessions_count,
                    "total_modules": total_modules_count,
                    "status": course_status,
                    "created_at": cohort_course.created_at,
                    "course_type": "cohort_specific"
                })
        
        return {
            "enrolled_courses": enrolled_courses,
            "total_courses": len(enrolled_courses)
        }
    except Exception as e:
        logger.error(f"Get enrolled courses error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch enrolled courses")

@router.get("/student/courses/{course_id}/modules")
async def get_student_course_modules(
    course_id: int,
    current_user_info = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Get modules for a specific course that the student is enrolled in"""
    try:
        from cohort_specific_models import CohortSpecificCourse, CohortCourseModule, CohortCourseSession
        
        # Determine role and student ID
        student_id = current_user_info["id"]
        role = current_user_info.get("role", "Student")
        is_staff = role in ["Admin", "Presenter", "Manager"]
        
        # Check if student is enrolled in this course using helper function
        if role == "Student":
            enrollment_status = get_student_enrollment_status(db, student_id, course_id)
            enrolled_regular_course_ids = enrollment_status["enrolled_regular_course_ids"]
            
            # Check cohort access for cohort-specific courses (auto-access)
            user_cohort_ids = [uc.cohort_id for uc in enrollment_status["user_cohorts"]]
            has_cohort_access = False
            is_cohort_course = False
            
            cohort_course = db.query(CohortSpecificCourse).filter(CohortSpecificCourse.id == course_id).first()
            if cohort_course and cohort_course.cohort_id in user_cohort_ids:
                has_cohort_access = True
                is_cohort_course = True
            
            if course_id not in enrolled_regular_course_ids and not has_cohort_access:
                raise HTTPException(status_code=403, detail="Not enrolled in this course")
            
            # Check payment status for regular courses
            if course_id in enrolled_regular_course_ids:
                enrollment = db.query(Enrollment).filter(
                    Enrollment.student_id == student_id,
                    Enrollment.course_id == course_id
                ).first()
                if enrollment and enrollment.payment_status == 'pending_payment':
                    raise HTTPException(status_code=402, detail="Payment required to access this course content")
        else:
            # Staff has access to everything
            has_cohort_access = False
            is_cohort_course = False
            
            # Check if it's a cohort-specific course
            cohort_course = db.query(CohortSpecificCourse).filter(CohortSpecificCourse.id == course_id).first()
            if cohort_course:
                is_cohort_course = True
                has_cohort_access = True
            
            enrolled_regular_course_ids = [course_id] if not is_cohort_course else []
        
        result = []
        
        # Check if it's a regular course
        if course_id in enrolled_regular_course_ids and not is_cohort_course:
            # Get modules for regular course
            modules = db.query(Module).filter(
                Module.course_id == course_id
            ).order_by(Module.week_number).all()
            
            for module in modules:
                # Get sessions for this module
                sessions = db.query(SessionModel).filter(
                    SessionModel.module_id == module.id
                ).order_by(SessionModel.session_number).all()
                
                # Get session data with resources and attendance
                session_data = []
                module_progress_sum = 0
                
                for s in sessions:
                    # Get resources for this session
                    resources = db.query(Resource).filter(Resource.session_id == s.id).all()
                    session_contents = db.query(SessionContent).filter(SessionContent.session_id == s.id).all()
                    
                    # Calculate progress
                    progress_pct, status, total_count, completed_count = calculate_student_session_progress(db, student_id, s.id)
                    module_progress_sum += progress_pct
                    
                    session_data.append({
                        "id": s.id,
                        "session_number": s.session_number,
                        "title": s.title,
                        "description": s.description,
                        "scheduled_time": s.scheduled_time,
                        "duration_minutes": s.duration_minutes,
                        "attended": status == "Completed",
                        "status": status,
                        "progress": progress_pct,
                        "resources_count": total_count,
                        "completed_resources": completed_count
                    })
                
                # Calculate module status
                module_status = "Not Started"
                if sessions:
                    avg_progress = module_progress_sum / len(sessions)
                    if avg_progress >= 100:
                        module_status = "Completed"
                    elif avg_progress > 0 or any(s["status"] == "Started" for s in session_data):
                        module_status = "Started"
                        
                    # Check/Update StudentModuleStatus
                    mod_status_record = db.query(StudentModuleStatus).filter(
                        StudentModuleStatus.student_id == student_id,
                        StudentModuleStatus.module_id == module.id
                    ).first()
                    
                    if not mod_status_record:
                        if module_status != "Not Started":
                            mod_status_record = StudentModuleStatus(
                                student_id=student_id,
                                module_id=module.id,
                                status=module_status,
                                started_at=datetime.utcnow() if module_status == "Started" else None,
                                completed_at=datetime.utcnow() if module_status == "Completed" else None
                            )
                            db.add(mod_status_record)
                            db.commit()
                    else:
                        if mod_status_record.status != module_status:
                            mod_status_record.status = module_status
                            if module_status == "Completed":
                                mod_status_record.completed_at = datetime.utcnow()
                            db.commit()
                else:
                    avg_progress = 0

                result.append({
                    "id": module.id,
                    "week_number": module.week_number,
                    "title": module.title,
                    "description": module.description,
                    "start_date": module.start_date,
                    "end_date": module.end_date,
                    "status": module_status,
                    "progress": round(avg_progress),
                    "sessions_count": len(sessions),
                    "sessions": session_data
                })
        
        # Check if it's a cohort-specific course
        elif has_cohort_access:
            # Get modules for cohort-specific course
            modules = db.query(CohortCourseModule).filter(
                CohortCourseModule.course_id == course_id
            ).order_by(CohortCourseModule.week_number).all()
            
            for module in modules:
                # Get sessions for this cohort module
                sessions = db.query(CohortCourseSession).filter(
                    CohortCourseSession.module_id == module.id
                ).order_by(CohortCourseSession.session_number).all()
                
                # Get session data with resources and attendance
                session_data = []
                module_progress_sum = 0
                
                for s in sessions:
                    # Get cohort session content
                    from cohort_specific_models import CohortSessionContent
                    session_contents = db.query(CohortSessionContent).filter(
                        CohortSessionContent.session_id == s.id
                    ).all()
                    
                    # Calculate progress
                    progress_pct, status, total_count, completed_count = calculate_student_session_progress(
                        db, 
                        student_id, 
                        s.id,
                        session_type="cohort"
                    )
                    module_progress_sum += progress_pct
                    
                    session_data.append({
                        "id": s.id,
                        "session_number": s.session_number,
                        "title": s.title,
                        "description": s.description,
                        "scheduled_time": s.scheduled_time,
                        "duration_minutes": s.duration_minutes,
                        "attended": status == "Completed",
                        "status": status,
                        "progress": progress_pct,
                        "resources_count": total_count,
                        "completed_resources": completed_count
                    })
                
                # Calculate module status
                module_status = "Not Started"
                avg_progress = 0
                if sessions:
                    avg_progress = module_progress_sum / len(sessions)
                    if avg_progress >= 100:
                        module_status = "Completed"
                    elif avg_progress > 0 or any(s["status"] == "Started" for s in session_data):
                        module_status = "Started"
                    
                    # Update StudentModuleStatus for cohort module
                    mod_status_record = db.query(StudentModuleStatus).filter(
                        StudentModuleStatus.student_id == student_id,
                        StudentModuleStatus.module_id == module.id,
                        StudentModuleStatus.module_type == "cohort"
                    ).first()
                    
                    if not mod_status_record:
                        if module_status != "Not Started":
                            mod_status_record = StudentModuleStatus(
                                student_id=student_id,
                                module_id=module.id,
                                module_type="cohort",
                                status=module_status,
                                started_at=datetime.utcnow() if module_status == "Started" else None,
                                completed_at=datetime.utcnow() if module_status == "Completed" else None
                            )
                            db.add(mod_status_record)
                            db.commit()
                    else:
                        if mod_status_record.status != module_status:
                            mod_status_record.status = module_status
                            if module_status == "Completed":
                                mod_status_record.completed_at = datetime.utcnow()
                            db.commit()
                
                result.append({
                    "id": module.id,
                    "week_number": module.week_number,
                    "title": module.title,
                    "description": module.description,
                    "start_date": module.start_date,
                    "end_date": module.end_date,
                    "status": module_status,
                    "progress": round(avg_progress),
                    "sessions_count": len(sessions),
                    "sessions": session_data
                })
        
        return {"modules": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get student course modules error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch course modules")

@router.get("/student/sessions/{session_id}")
async def get_student_session(
    session_id: int,
    current_user_info = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Get session details for a student - handles both regular and cohort sessions"""
    try:
        from cohort_specific_models import CohortCourseSession, CohortCourseModule, CohortSessionContent, CohortSpecificCourse
        
        # Determine role and student ID
        student_id = current_user_info["id"]
        role = current_user_info.get("role", "Student")
        is_staff = role in ["Admin", "Presenter", "Manager"]
        
        # Try to get regular session first
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        
        if session:
            # Handle regular session
            module = db.query(Module).filter(Module.id == session.module_id).first()
            if not module:
                raise HTTPException(status_code=404, detail="Module not found")
            
            # Check enrollment for students
            if role == "Student":
                enrollment_status = get_student_enrollment_status(db, student_id, module.course_id)
                enrolled_regular_course_ids = enrollment_status["enrolled_regular_course_ids"]
                
                if module.course_id not in enrolled_regular_course_ids:
                    raise HTTPException(status_code=403, detail="Not enrolled in this course")
                
                # Check payment status
                enrollment = db.query(Enrollment).filter(
                    Enrollment.student_id == student_id,
                    Enrollment.course_id == module.course_id
                ).first()
                if enrollment and enrollment.payment_status == 'pending_payment':
                    raise HTTPException(status_code=402, detail="Payment required to access this session content")
                
                # Check if module is locked
                if module.start_date and module.start_date > datetime.now():
                    raise HTTPException(
                        status_code=403, 
                        detail=f"This module is locked until {module.start_date.strftime('%Y-%m-%d')}"
                    )
            
            # Get session resources
            resources = db.query(Resource).filter(Resource.session_id == session_id).all()
            resource_list = []
            
            for resource in resources:
                resource_list.append({
                    "id": resource.id,
                    "title": resource.title,
                    "description": resource.description,
                    "resource_type": resource.resource_type,
                    "file_type": resource.resource_type, # Normalize for frontend
                    "file_path": resource.file_path,
                    "file_size": resource.file_size,
                    "content_type": "RESOURCE",
                    "created_at": resource.created_at
                })
            
            # Get session content
            session_contents = db.query(SessionContent).filter(SessionContent.session_id == session_id).all()
            
            for content in session_contents:
                if content.content_type == 'MEETING_LINK':
                    resource_list.append({
                        "id": content.id,
                        "title": content.title,
                        "description": content.description,
                        "content_type": "MEETING_LINK",
                        "meeting_url": content.meeting_url,
                        "scheduled_time": content.scheduled_time,
                        "is_locked": content.scheduled_time > datetime.now() if content.scheduled_time else False,
                        "created_at": content.created_at
                    })
                else:
                    resource_list.append({
                        "id": content.id,
                        "title": content.title,
                        "description": content.description,
                        "content_type": content.content_type,
                        "resource_type": content.content_type, # Normalize for frontend
                        "file_type": content.file_type,
                        "file_path": content.file_path,
                        "file_size": content.file_size,
                        "created_at": content.created_at
                    })
            
            # Get session progress and status
            if role == "Student":
                progress_pct, status, total_count, completed_count = calculate_student_session_progress(db, student_id, session_id, session_type="global")
            else:
                progress_pct, status, total_count, completed_count = 0, "Staff View", 0, 0
            
            # Get associated quizzes
            quizzes_list = []
            try:
                from assignment_quiz_tables import Quiz, QuizAttempt
                quizzes = db.query(Quiz).filter(
                    Quiz.session_id == session_id,
                    Quiz.session_type == "global"
                ).all()
                for q in quizzes:
                    attempt = None
                    if role == "Student":
                        attempt = db.query(QuizAttempt).filter(
                            QuizAttempt.quiz_id == q.id,
                            QuizAttempt.student_id == student_id
                        ).first()

                    score = None
                    if attempt and (attempt.status == QuizStatus.COMPLETED or attempt.status == "COMPLETED"):
                        result = db.query(QuizResult).filter(
                            QuizResult.attempt_id == attempt.id
                        ).first()
                        if result:
                            score = result.marks_obtained
                        
                    quizzes_list.append({
                        "id": q.id,
                        "title": q.title,
                        "description": q.description,
                        "time_limit": q.time_limit_minutes,
                        "total_marks": q.total_marks,
                        "attempted": attempt is not None,
                        "status": attempt.status if attempt else "NOT_ATTEMPTED",
                        "score": score
                    })
            except ImportError:
                pass

            return {
                "id": session.id,
                "title": session.title,
                "description": session.description,
                "session_number": session.session_number,
                "scheduled_time": session.scheduled_time,
                "duration_minutes": session.duration_minutes,
                "zoom_link": session.zoom_link,
                "recording_url": session.recording_url,
                "syllabus_content": session.syllabus_content,
                "resources": resource_list,
                "quizzes": quizzes_list,
                "status": status,
                "progress": progress_pct,
                "resources_count": total_count,
                "completed_resources": completed_count,
                "module": {
                    "id": module.id,
                    "title": module.title,
                    "week_number": module.week_number
                },
                "session_type": "regular"
            }
        
        # Try cohort session if regular session not found
        cohort_session = db.query(CohortCourseSession).filter(CohortCourseSession.id == session_id).first()
        
        if cohort_session:
            # Handle cohort session
            cohort_module = db.query(CohortCourseModule).filter(CohortCourseModule.id == cohort_session.module_id).first()
            if not cohort_module:
                raise HTTPException(status_code=404, detail="Module not found")
            
            # Check cohort access for students
            if role == "Student":
                # Get student's cohort
                student = db.query(User).filter(User.id == student_id).first()
                if not student or not student.cohort_id:
                    raise HTTPException(status_code=403, detail="Not enrolled in this course")
                
                # Check if the course belongs to student's cohort
                cohort_course = db.query(CohortSpecificCourse).filter(
                    CohortSpecificCourse.id == cohort_module.course_id
                ).first()
                
                if not cohort_course or cohort_course.cohort_id != student.cohort_id:
                    raise HTTPException(status_code=403, detail="Not enrolled in this course")

                # Check if cohort module is locked
                if cohort_module.start_date and cohort_module.start_date > datetime.now():
                    raise HTTPException(
                        status_code=403, 
                        detail=f"This module is locked until {cohort_module.start_date.strftime('%Y-%m-%d')}"
                    )
            
            # Get cohort session content
            from cohort_specific_models import CohortSessionContent, CohortCourseResource
            session_contents = db.query(CohortSessionContent).filter(CohortSessionContent.session_id == session_id).all()
            cohort_resources = db.query(CohortCourseResource).filter(CohortCourseResource.session_id == session_id).all()
            resource_list = []
            
            # Add cohort resources
            for resource in cohort_resources:
                resource_list.append({
                    "id": resource.id,
                    "title": resource.title,
                    "description": resource.description,
                    "resource_type": resource.resource_type,
                    "file_type": resource.resource_type, # Normalize for frontend
                    "file_path": resource.file_path,
                    "file_size": resource.file_size,
                    "content_type": "RESOURCE",
                    "created_at": resource.created_at
                })
                
            for content in session_contents:
                if content.content_type == 'MEETING_LINK':
                    resource_list.append({
                        "id": content.id,
                        "title": content.title,
                        "description": content.description,
                        "content_type": "MEETING_LINK",
                        "meeting_url": content.meeting_url,
                        "scheduled_time": content.scheduled_time,
                        "is_locked": content.scheduled_time > datetime.now() if content.scheduled_time else False,
                        "created_at": content.created_at
                    })
                else:
                    resource_list.append({
                        "id": content.id,
                        "title": content.title,
                        "description": content.description,
                        "content_type": content.content_type,
                        "resource_type": content.content_type, # Normalize for frontend
                        "file_type": content.file_type,
                        "file_path": content.file_path,
                        "file_size": content.file_size,
                        "created_at": content.created_at
                    })
            
            # Get session progress and status
            if role == "Student":
                progress_pct, status, total_count, completed_count = calculate_student_session_progress(db, student_id, session_id, session_type="cohort")
            else:
                progress_pct, status, total_count, completed_count = 0, "Staff View", 0, 0
            
            # Get associated quizzes for cohort session
            quizzes_list = []
            try:
                from assignment_quiz_tables import Quiz, QuizAttempt
                quizzes = db.query(Quiz).filter(
                    Quiz.session_id == session_id,
                    Quiz.session_type == "cohort"
                ).all()
                for q in quizzes:
                    attempt = None
                    if role == "Student":
                        attempt = db.query(QuizAttempt).filter(
                            QuizAttempt.quiz_id == q.id,
                            QuizAttempt.student_id == student_id
                        ).first()
                    score = None
                    if attempt and (attempt.status == QuizStatus.COMPLETED or attempt.status == "COMPLETED"):
                        result = db.query(QuizResult).filter(
                            QuizResult.attempt_id == attempt.id
                        ).first()
                        if result:
                            score = result.marks_obtained

                    quizzes_list.append({
                        "id": q.id,
                        "title": q.title,
                        "description": q.description,
                        "time_limit": q.time_limit_minutes,
                        "total_marks": q.total_marks,
                        "attempted": attempt is not None,
                        "status": attempt.status if attempt else "NOT_ATTEMPTED",
                        "score": score
                    })
            except ImportError:
                pass
            
            return {
                "id": cohort_session.id,
                "title": cohort_session.title,
                "description": cohort_session.description,
                "session_number": cohort_session.session_number,
                "scheduled_time": cohort_session.scheduled_time,
                "duration_minutes": cohort_session.duration_minutes,
                "zoom_link": cohort_session.zoom_link,
                "recording_url": cohort_session.recording_url,
                "syllabus_content": cohort_session.syllabus_content,
                "resources": resource_list,
                "quizzes": quizzes_list,
                "status": status,
                "progress": progress_pct,
                "resources_count": total_count,
                "completed_resources": completed_count,
                "module": {
                    "id": cohort_module.id,
                    "title": cohort_module.title,
                    "week_number": cohort_module.week_number
                },
                "session_type": "cohort"
            }
        

        # Session not found in either table
        raise HTTPException(status_code=404, detail="Session not found")

        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get student session error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch session")

@router.get("/student/assignments")
async def get_student_assignments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all assignments for student's enrolled courses"""
    try:
        from cohort_specific_models import CohortSpecificCourse, CohortCourseModule, CohortCourseSession, CohortSpecificEnrollment
        
        assignments = []
        
        # Get student's enrollment status
        enrollment_status = get_student_enrollment_status(db, current_user.id)
        enrolled_regular_course_ids = enrollment_status["enrolled_regular_course_ids"]
        enrolled_cohort_course_ids = enrollment_status["enrolled_cohort_course_ids"]
        
        # Fetch assignments from global courses
        if enrolled_regular_course_ids:
            courses = db.query(Course).filter(Course.id.in_(enrolled_regular_course_ids)).all()
            
            for course in courses:
                modules = db.query(Module).filter(Module.course_id == course.id).all()
                for module in modules:
                    sessions = db.query(SessionModel).filter(SessionModel.module_id == module.id).all()
                    for session in sessions:
                        course_assignments = db.query(Assignment).filter(
                            Assignment.session_id == session.id,
                            Assignment.session_type == "global",
                            Assignment.is_active == True
                        ).all()
                        
                        for assignment in course_assignments:
                            submission = db.query(AssignmentSubmission).filter(
                                AssignmentSubmission.assignment_id == assignment.id,
                                AssignmentSubmission.student_id == current_user.id
                            ).first()
                            
                            grade = None
                            if submission:
                                from assignment_quiz_models import AssignmentGrade
                                grade_record = db.query(AssignmentGrade).filter(
                                    AssignmentGrade.submission_id == submission.id
                                ).first()
                                if grade_record:
                                    grade = {
                                        "marks_obtained": grade_record.marks_obtained,
                                        "total_marks": grade_record.total_marks,
                                        "percentage": grade_record.percentage,
                                        "feedback": grade_record.feedback
                                    }
                            
                            assignments.append({
                                "id": assignment.id,
                                "title": assignment.title,
                                "description": assignment.description,
                                "course_title": course.title,
                                "session_title": session.title,
                                "module_title": module.title,
                                "due_date": assignment.due_date,
                                "total_marks": assignment.total_marks,
                                "submission_type": assignment.submission_type.value if assignment.submission_type else "FILE",
                                "submitted": submission is not None,
                                "submission_id": submission.id if submission else None,
                                "submitted_at": submission.submitted_at if submission else None,
                                "status": submission.status.value if submission else "PENDING",
                                "grade": grade,
                                "session_type": "global",
                                "created_at": assignment.created_at
                            })
        
        # Fetch assignments from cohort-specific courses
        if enrolled_cohort_course_ids:
            cohort_courses = db.query(CohortSpecificCourse).filter(
                CohortSpecificCourse.id.in_(enrolled_cohort_course_ids)
            ).all()
            
            for course in cohort_courses:
                modules = db.query(CohortCourseModule).filter(
                    CohortCourseModule.course_id == course.id
                ).all()
                for module in modules:
                    sessions = db.query(CohortCourseSession).filter(
                        CohortCourseSession.module_id == module.id
                    ).all()
                    for session in sessions:
                        course_assignments = db.query(Assignment).filter(
                            Assignment.session_id == session.id,
                            Assignment.session_type == "cohort",
                            Assignment.is_active == True
                        ).all()
                        
                        for assignment in course_assignments:
                            submission = db.query(AssignmentSubmission).filter(
                                AssignmentSubmission.assignment_id == assignment.id,
                                AssignmentSubmission.student_id == current_user.id
                            ).first()
                            
                            grade = None
                            if submission:
                                from assignment_quiz_models import AssignmentGrade
                                grade_record = db.query(AssignmentGrade).filter(
                                    AssignmentGrade.submission_id == submission.id
                                ).first()
                                if grade_record:
                                    grade = {
                                        "marks_obtained": grade_record.marks_obtained,
                                        "total_marks": grade_record.total_marks,
                                        "percentage": grade_record.percentage,
                                        "feedback": grade_record.feedback
                                    }
                            
                            assignments.append({
                                "id": assignment.id,
                                "title": assignment.title,
                                "description": assignment.description,
                                "course_title": course.title,
                                "session_title": session.title,
                                "module_title": module.title,
                                "due_date": assignment.due_date,
                                "total_marks": assignment.total_marks,
                                "submission_type": assignment.submission_type.value if assignment.submission_type else "FILE",
                                "submitted": submission is not None,
                                "submission_id": submission.id if submission else None,
                                "submitted_at": submission.submitted_at if submission else None,
                                "status": submission.status.value if submission else "PENDING",
                                "grade": grade,
                                "session_type": "cohort",
                                "created_at": assignment.created_at
                            })
        
        # Sort by due date
        assignments.sort(key=lambda x: x["due_date"])
        
        return {
            "assignments": assignments,
            "total": len(assignments)
        }
    except Exception as e:
        import traceback
        logger.error(f"Get student assignments error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to fetch assignments")


@router.post("/student/assignments/{assignment_id}/submit")
async def submit_assignment(
    assignment_id: int,
    submission_text: str = None,
    file: UploadFile = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit an assignment"""
    try:
        from fastapi import UploadFile, File, Form
        import os
        from pathlib import Path
        
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Check if already submitted
        existing = db.query(AssignmentSubmission).filter(
            AssignmentSubmission.assignment_id == assignment_id,
            AssignmentSubmission.student_id == current_user.id
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Assignment already submitted")
        
        file_path = None
        if file:
            upload_dir = Path("uploads/assignments")
            upload_dir.mkdir(parents=True, exist_ok=True)
            file_path = upload_dir / f"{current_user.id}_{assignment_id}_{file.filename}"
            with open(file_path, "wb") as f:
                f.write(await file.read())
            file_path = str(file_path)
        
        submission = AssignmentSubmission(
            assignment_id=assignment_id,
            student_id=current_user.id,
            submission_text=submission_text,
            file_path=file_path,
            submitted_at=datetime.now(),
            status="SUBMITTED"
        )
        
        db.add(submission)
        db.commit()
        db.refresh(submission)
        
        return {"message": "Assignment submitted successfully", "submission_id": submission.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Submit assignment error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to submit assignment")

@router.get("/student/quizzes")
async def get_student_quizzes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all quizzes for student's enrolled courses"""
    try:
        from assignment_quiz_models import Quiz, QuizAttempt
        
        student = db.query(User).filter(User.id == current_user.id).first()
        if not student or not student.cohort_id:
            return {"quizzes": [], "total": 0}
        
        cohort_courses = db.query(CohortCourse).filter(
            CohortCourse.cohort_id == student.cohort_id
        ).all()
        
        if not cohort_courses:
            return {"quizzes": [], "total": 0}
        
        course_ids = [cc.course_id for cc in cohort_courses]
        quizzes = []
        courses = db.query(Course).filter(Course.id.in_(course_ids)).all()
        
        for course in courses:
            modules = db.query(Module).filter(Module.course_id == course.id).all()
            for module in modules:
                sessions = db.query(SessionModel).filter(SessionModel.module_id == module.id).all()
                for session in sessions:
                    course_quizzes = db.query(Quiz).filter(
                        Quiz.session_id == session.id,
                        Quiz.is_active == True
                    ).all()
                    
                    for quiz in course_quizzes:
                        attempt = db.query(QuizAttempt).filter(
                            QuizAttempt.quiz_id == quiz.id,
                            QuizAttempt.student_id == current_user.id
                        ).first()
                        
                        quizzes.append({
                            "id": quiz.id,
                            "title": quiz.title,
                            "description": quiz.description,
                            "course_title": course.title,
                            "session_title": session.title,
                            "module_title": module.title,
                            "duration_minutes": quiz.duration_minutes,
                            "total_marks": quiz.total_marks,
                            "attempted": attempt is not None,
                            "attempt_id": attempt.id if attempt else None,
                            "score": attempt.score if attempt else None,
                            "created_at": quiz.created_at
                        })
        
        return {"quizzes": quizzes, "total": len(quizzes)}
    except Exception as e:
        logger.error(f"Get student quizzes error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch quizzes")


@router.get("/student/meeting-links")
async def get_student_meeting_links(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get meeting links from all courses the student is enrolled in"""
    try:
        from cohort_specific_models import CohortSpecificCourse, CohortCourseModule, CohortCourseSession, CohortSessionContent
        enrollment_status = get_student_enrollment_status(db, current_user.id)
        enrolled_regular_course_ids = enrollment_status["enrolled_regular_course_ids"]
        enrolled_cohort_course_ids = enrollment_status["enrolled_cohort_course_ids"]

        result = []

        # Fetch meeting links from regular enrolled courses
        for course_id in enrolled_regular_course_ids:
            course = db.query(Course).filter(Course.id == course_id).first()
            if not course:
                continue
            modules = db.query(Module).order_by(Module.week_number).filter(Module.course_id == course_id).all()
            for module in modules:
                sessions = db.query(SessionModel).filter(SessionModel.module_id == module.id).all()
                for session in sessions:
                    meetings = (
                        db.query(SessionContent)
                        .filter(
                            SessionContent.session_id == session.id,
                            SessionContent.content_type == "MEETING_LINK",
                            SessionContent.meeting_url.isnot(None),
                            SessionContent.meeting_url != ""
                        )
                        .all()
                    )
                    for m in meetings:
                        result.append({
                            "id": m.id,
                            "title": m.title or session.title,
                            "course_name": course.title,
                            "week_number": module.week_number,
                            "module_title": module.title,
                            "session_title": session.title,
                            "session_number": session.session_number,
                            "meeting_url": m.meeting_url,
                            "scheduled_time": m.scheduled_time.isoformat() if m.scheduled_time else None,
                            "created_at": m.created_at.isoformat() if m.created_at else None,
                        })

        # Fetch meeting links from cohort-specific courses
        if enrolled_cohort_course_ids:
            cohort_courses = db.query(CohortSpecificCourse).filter(
                CohortSpecificCourse.id.in_(enrolled_cohort_course_ids)
            ).all()
            for course in cohort_courses:
                modules = db.query(CohortCourseModule).order_by(CohortCourseModule.week_number).filter(CohortCourseModule.course_id == course.id).all()
                for module in modules:
                    sessions = db.query(CohortCourseSession).filter(CohortCourseSession.module_id == module.id).all()
                    for session in sessions:
                        meetings = (
                            db.query(CohortSessionContent)
                            .filter(
                                CohortSessionContent.session_id == session.id,
                                CohortSessionContent.content_type == "MEETING_LINK",
                                CohortSessionContent.meeting_url.isnot(None),
                                CohortSessionContent.meeting_url != ""
                            )
                            .all()
                        )
                        for m in meetings:
                            result.append({
                                "id": f"cohort_{m.id}",
                                "title": m.title or session.title,
                                "course_name": course.title,
                                "week_number": module.week_number,
                                "module_title": module.title,
                                "session_title": session.title,
                                "session_number": session.session_number,
                                "meeting_url": m.meeting_url,
                                "scheduled_time": m.scheduled_time.isoformat() if m.scheduled_time else None,
                                "created_at": m.created_at.isoformat() if m.created_at else None,
                            })

        # Sort: meetings with a scheduled_time first (soonest first), then by created_at
        result.sort(key=lambda x: (
            x["scheduled_time"] is None,
            x["scheduled_time"] or x["created_at"] or ""
        ))

        return {"meetings": result, "total": len(result)}
    except Exception as e:
        logger.error(f"Get student meeting links error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch meeting links")