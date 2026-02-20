from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional
from database import get_db, Course, Module, Session, Enrollment, CohortCourse, Cohort
from auth import get_current_admin_or_presenter
from schemas import CourseCreate, CourseUpdate
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["course_management"])

# Import logging functions
from logging_utils import log_admin_action, log_presenter_action

@router.post("/courses")
async def create_course(
    course_data: CourseCreate, 
    current_user = Depends(get_current_admin_or_presenter), 
    db: Session = Depends(get_db)
):
    # Determine approval status based on role
    approval_status = 'approved'
    user_role = getattr(current_user, 'role', None)
    
    # Check roles for non-User objects (Admin, Manager, Presenter models)
    from database import Admin, Manager, Presenter, CourseAssignment
    
    is_admin = db.query(Admin).filter(Admin.id == current_user.id).first() is not None
    is_manager = db.query(Manager).filter(Manager.id == current_user.id).first() is not None
    is_presenter = db.query(Presenter).filter(Presenter.id == current_user.id).first() is not None
    
    if is_presenter and not (is_admin or is_manager):
        approval_status = 'pending'
    
    try:
        course = Course(
            title=course_data.title,
            description=course_data.description,
            duration_weeks=course_data.duration_weeks,
            sessions_per_week=course_data.sessions_per_week,
            is_active=course_data.is_active,
            approval_status=approval_status,
            payment_type=course_data.payment_type,
            default_price=course_data.default_price
        )
        db.add(course)
        db.flush() # Get course ID
        
        # Handle initial assignments
        if course_data.assignments:
            for assignment_data in course_data.assignments:
                assignment = CourseAssignment(
                    course_id=course.id,
                    assignment_type=assignment_data.assignment_type,
                    user_id=assignment_data.user_id,
                    college=assignment_data.college,
                    cohort_id=assignment_data.cohort_id,
                    assignment_mode=assignment_data.assignment_mode,
                    amount=assignment_data.amount,
                    assigned_by=current_user.id if is_admin else None # Explicitly track admin as assigner if applicable
                )
                db.add(assignment)
        
        db.commit()
        db.refresh(course)
        
        # Auto-setup course structure
        await auto_setup_course_structure(
            course.id, 
            course_data.duration_weeks, 
            course_data.sessions_per_week, 
            db
        )
        
        # Log course creation
        if is_admin:
            log_admin_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action_type="CREATE",
                resource_type="COURSE",
                resource_id=course.id,
                details=f"Created course: {course.title} (Status: {approval_status})"
            )
        elif is_presenter:
            log_presenter_action(
                presenter_id=current_user.id,
                presenter_username=current_user.username,
                action_type="CREATE",
                resource_type="COURSE",
                resource_id=course.id,
                details=f"Created course: {course.title} (Status: {approval_status})"
            )
        
        return {
            "message": "Course created successfully", 
            "course_id": course.id,
            "approval_status": approval_status
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Create course error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create course")

async def auto_setup_course_structure(
    course_id: int, 
    duration_weeks: int, 
    sessions_per_week: int, 
    db: Session
):
    """Auto-generate course structure with weeks, modules, and sessions"""
    try:
        # Create modules for each week
        for week in range(1, duration_weeks + 1):
            module = Module(
                course_id=course_id,
                week_number=week,
                title=f"Week {week} - Module",
                description=f"Learning objectives and content for week {week}"
            )
            db.add(module)
            db.flush()  # Get the module ID
            
            # Create sessions for each module
            for session_num in range(1, sessions_per_week + 1):
                session = Session(
                    module_id=module.id,
                    session_number=session_num,
                    title=f"Week {week} - Session {session_num}",
                    description=f"Session {session_num} content for week {week}",
                    duration_minutes=120
                )
                db.add(session)
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise e

@router.put("/courses/{course_id}/approval")
async def update_course_approval(
    course_id: int,
    approval_data: dict, # {"status": "approved" | "rejected"}
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Approve or reject a course - Restricted to Admin or Manager"""
    from database import Admin, Manager
    
    is_admin = db.query(Admin).filter(Admin.id == current_user.id).first() is not None
    is_manager = db.query(Manager).filter(Manager.id == current_user.id).first() is not None
    
    if not (is_admin or is_manager):
        raise HTTPException(status_code=403, detail="Only Admins or Managers can approve courses")
    
    new_status = approval_data.get("status")
    if new_status not in ['approved', 'rejected']:
        raise HTTPException(status_code=400, detail="Invalid status. Must be 'approved' or 'rejected'")
    
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    course.approval_status = new_status
    db.commit()
    
    # Log the approval action
    if is_admin:
        log_admin_action(
            admin_id=current_user.id,
            admin_username=current_user.username,
            action_type="APPROVAL",
            resource_type="COURSE",
            resource_id=course.id,
            details=f"Course {course.title} {new_status}"
        )
    
    return {"message": f"Course {new_status} successfully", "status": new_status}

@router.get("/courses")
async def get_courses(
    page: int = 1,
    limit: int = 10,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        from database import Admin, Manager, Presenter
        is_admin = db.query(Admin).filter(Admin.id == current_user.id).first() is not None
        is_manager = db.query(Manager).filter(Manager.id == current_user.id).first() is not None
        is_presenter = db.query(Presenter).filter(Presenter.id == current_user.id).first() is not None
        
        query = db.query(Course)
        
        # Filtering logic based on role
        if is_presenter and not (is_admin or is_manager):
            # Presenters see their own courses or approved courses
            # Note: Legacy instructor_id is used for "own" courses here
            query = query.filter(or_(Course.approval_status == 'approved', Course.instructor_id == current_user.id))
        # Admins and Managers see everything
        
        if search:
            query = query.filter(Course.title.ilike(f"%{search}%"))
        if is_active is not None:
            query = query.filter(Course.is_active == is_active)
            
        total_count = query.count()
        courses = query.offset((page - 1) * limit).limit(limit).all()
        
        # ... (rest of the logic to return course details)
        
        result = []
        for course in courses:
            enrolled_count = db.query(Enrollment).filter(Enrollment.course_id == course.id).count()
            modules_count = db.query(Module).filter(Module.course_id == course.id).count()
            
            max_week = db.query(func.max(Module.week_number)).filter(Module.course_id == course.id).scalar()
            duration_weeks = max_week if max_week else course.duration_weeks
            
            # Check if this course is a cohort-specific course (created for cohort, not just assigned)
            # Simple logic: if course is only in one cohort, it's likely cohort-specific
            cohort_assignments = db.query(CohortCourse).filter(CohortCourse.course_id == course.id).all()
            
            cohort_info = None
            is_cohort_specific = False
            
            if len(cohort_assignments) == 1:
                # Only in one cohort - likely created specifically for that cohort
                cohort_assignment = cohort_assignments[0]
                cohort = db.query(Cohort).filter(Cohort.id == cohort_assignment.cohort_id).first()
                if cohort:
                    is_cohort_specific = True
                    cohort_info = {
                        "cohort_id": cohort.id,
                        "cohort_name": cohort.name
                    }
            
            result.append({
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "duration_weeks": duration_weeks,
                "sessions_per_week": course.sessions_per_week,
                "is_active": course.is_active,
                "approval_status": course.approval_status,
                "payment_type": course.payment_type,
                "default_price": course.default_price,
                "enrolled_students": enrolled_count,
                "modules_count": modules_count,
                "created_at": course.created_at,
                "cohort_info": cohort_info,
                "is_cohort_course": is_cohort_specific
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

@router.put("/courses/{course_id}")
async def update_course(
    course_id: int,
    course_data: CourseUpdate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        update_data = course_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(course, field, value)
        
        db.commit()
        
        # Log course update
        from database import Admin, Presenter
        if hasattr(current_user, 'username') and db.query(Admin).filter(Admin.id == current_user.id).first():
            log_admin_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action_type="UPDATE",
                resource_type="COURSE",
                resource_id=course_id,
                details=f"Updated course: {course.title}"
            )
        elif hasattr(current_user, 'username') and db.query(Presenter).filter(Presenter.id == current_user.id).first():
            log_presenter_action(
                presenter_id=current_user.id,
                presenter_username=current_user.username,
                action_type="UPDATE",
                resource_type="COURSE",
                resource_id=course_id,
                details=f"Updated course: {course.title}"
            )
        
        return {"message": "Course updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update course error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update course")

@router.delete("/courses/{course_id}")
async def delete_course(
    course_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        from database import Admin, Manager, Presenter, Mentor, User, CohortCourse, Certificate, Resource, SessionContent, Attendance, Forum, ForumPost
        
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Get user role
        user_role = None
        if hasattr(current_user, 'username'):
            if db.query(Admin).filter(Admin.id == current_user.id).first():
                user_role = "Admin"
            elif db.query(Manager).filter(Manager.id == current_user.id).first():
                user_role = "Manager"
            elif db.query(Presenter).filter(Presenter.id == current_user.id).first():
                user_role = "Presenter"
            elif db.query(Mentor).filter(Mentor.id == current_user.id).first():
                user_role = "Mentor"
            else:
                user_check = db.query(User).filter(User.id == current_user.id).first()
                if user_check:
                    user_role = user_check.role
        
        course_title = course.title
        
        # Delete related records in correct order
        db.query(CohortCourse).filter(CohortCourse.course_id == course_id).delete()
        db.query(Enrollment).filter(Enrollment.course_id == course_id).delete()
        db.query(Certificate).filter(Certificate.course_id == course_id).delete()
        
        # Delete modules and their related content
        modules = db.query(Module).filter(Module.course_id == course_id).all()
        for module in modules:
            sessions = db.query(Session).filter(Session.module_id == module.id).all()
            for session in sessions:
                db.query(Attendance).filter(Attendance.session_id == session.id).delete()
                db.query(Resource).filter(Resource.session_id == session.id).delete()
                db.query(SessionContent).filter(SessionContent.session_id == session.id).delete()
            
            db.query(Session).filter(Session.module_id == module.id).delete()
            
            forums = db.query(Forum).filter(Forum.module_id == module.id).all()
            for forum in forums:
                db.query(ForumPost).filter(ForumPost.forum_id == forum.id).delete()
            db.query(Forum).filter(Forum.module_id == module.id).delete()
        
        db.query(Module).filter(Module.course_id == course_id).delete()
        db.delete(course)
        db.commit()
        
        # Log course deletion
        if user_role == "Admin":
            log_admin_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action_type="DELETE",
                resource_type="COURSE",
                resource_id=course_id,
                details=f"Deleted course: {course_title}"
            )
        elif user_role == "Manager":
            log_admin_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action_type="DELETE",
                resource_type="COURSE",
                resource_id=course_id,
                details=f"Manager deleted course: {course_title}"
            )
        
        return {"message": "Course deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete course error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete course")