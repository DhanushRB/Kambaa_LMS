from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, and_
from typing import Optional
from database import get_db, Course, Module, Session as SessionModel, CohortCourse, CourseAssignment
from auth import get_current_admin_or_presenter
from schemas import CourseCreate, CourseUpdate
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/courses", tags=["Global Courses"])

# Import logging functions
from main import log_admin_action, log_presenter_action

@router.post("/")
async def create_global_course(
    course_data: CourseCreate, 
    current_user = Depends(get_current_admin_or_presenter), 
    db: Session = Depends(get_db)
):
    """Create a global course (visible to all users, not cohort-specific)"""
    try:
        # Determine approval status based on role
        is_admin = hasattr(current_user, 'role') and current_user.role == "Admin"
        # If not explicit admin role attribute, check Admin table
        if not is_admin:
            from database import Admin
            is_admin = db.query(Admin).filter(Admin.id == current_user.id).first() is not None

        approval_status = 'approved' if is_admin else 'pending'
        is_active = course_data.is_active if is_admin else False
        
        # Non-admins cannot set payment details during creation (Admin does it during approval)
        payment_type = course_data.payment_type if is_admin else 'free'
        default_price = course_data.default_price if is_admin else 0.0

        course = Course(
            title=course_data.title,
            description=course_data.description,
            duration_weeks=course_data.duration_weeks,
            sessions_per_week=course_data.sessions_per_week,
            is_active=is_active,
            approval_status=approval_status,
            payment_type=payment_type,
            default_price=default_price
        )
        db.add(course)
        db.commit()
        db.refresh(course)

        # Create Approval Request for non-admins
        if not is_admin:
            try:
                from approval_models import ApprovalRequest, OperationType, ApprovalStatus, EntityStatus
                import json
                
                approval_request = ApprovalRequest(
                    requester_id=current_user.id,
                    operation_type=OperationType.CREATE,
                    target_entity_type="course",
                    target_entity_id=course.id,
                    operation_data=json.dumps({"title": course.title}),
                    reason="New course creation requires admin approval and payment configuration.",
                    status=ApprovalStatus.PENDING
                )
                db.add(approval_request)
                db.flush()

                entity_status = EntityStatus(
                    entity_type="course",
                    entity_id=course.id,
                    status="pending_approval",
                    approval_request_id=approval_request.id
                )
                db.add(entity_status)
                db.commit()
                logger.info(f"Approval request created for course {course.id} by user {current_user.id}")
            except Exception as e:
                logger.error(f"Failed to create approval request for course {course.id}: {str(e)}")
                # We continue since the course is created as inactive/pending anyway
        
        # Auto-setup course structure
        await auto_setup_global_course_structure(
            course.id, 
            course_data.duration_weeks, 
            course_data.sessions_per_week, 
            db
        )

        # Handle Course Assignments
        try:
            from database import CourseAssignment
            if course_data.assignments:
                for assignment in course_data.assignments:
                    new_assignment = CourseAssignment(
                        course_id=course.id,
                        assignment_type=assignment.assignment_type,
                        user_id=assignment.user_id,
                        college=assignment.college,
                        cohort_id=assignment.cohort_id,
                        assignment_mode=assignment.assignment_mode,
                        amount=assignment.amount,
                        assigned_by=current_user.id if hasattr(current_user, 'id') else None
                    )
                    db.add(new_assignment)
                db.flush()
        except Exception as e:
            logger.error(f"Error saving assignments: {str(e)}")
            # Don't fail the whole creation for this, but log it
        
        # Log course creation
        from database import Admin, Presenter
        if hasattr(current_user, 'username') and db.query(Admin).filter(Admin.id == current_user.id).first():
            log_admin_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action_type="CREATE",
                resource_type="GLOBAL_COURSE",
                resource_id=course.id,
                details=f"Created global course: {course.title} ({course_data.duration_weeks} weeks)"
            )
        elif hasattr(current_user, 'username') and db.query(Presenter).filter(Presenter.id == current_user.id).first():
            log_presenter_action(
                presenter_id=current_user.id,
                presenter_username=current_user.username,
                action_type="CREATE",
                resource_type="GLOBAL_COURSE",
                resource_id=course.id,
                details=f"Created global course: {course.title} ({course_data.duration_weeks} weeks)"
            )
        
        success_msg = "Global course created successfully" if is_admin else "Course created and sent for Admin approval"
        return {
            "message": success_msg, 
            "course_id": course.id,
            "is_global": True,
            "approval_status": approval_status
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Create global course error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create global course")

async def auto_setup_global_course_structure(
    course_id: int, 
    duration_weeks: int, 
    sessions_per_week: int, 
    db: Session
):
    """Auto-generate global course structure with weeks, modules, and sessions"""
    try:
        for week in range(1, duration_weeks + 1):
            module = Module(
                course_id=course_id,
                week_number=week,
                title=f"Week {week} - Module",
                description=f"Learning objectives and content for week {week}"
            )
            db.add(module)
            db.flush()
            
            for session_num in range(1, sessions_per_week + 1):
                session = SessionModel(
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

@router.get("/")
async def get_global_courses(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    current_user = Depends(get_current_admin_or_presenter), 
    db: Session = Depends(get_db)
):
    """Get global courses only (excludes cohort-specific courses)"""
    try:
        # Get courses that are NOT cohort-specific
        # A course is global if it's either not assigned to any cohort OR assigned to multiple cohorts
        query = db.query(Course)
        
        if search:
            query = query.filter(
                or_(
                    Course.title.contains(search),
                    Course.description.contains(search)
                )
            )
        
        total = query.count()
        courses = query.offset((page - 1) * limit).limit(limit).all()
        
        result = []
        for course in courses:
            # Check cohort assignments for display purposes only
            cohort_assignments = db.query(CohortCourse).filter(CohortCourse.course_id == course.id).all()
            
            modules_count = db.query(Module).filter(Module.course_id == course.id).count()
            max_week = db.query(func.max(Module.week_number)).filter(Module.course_id == course.id).scalar()
            duration_weeks = max_week if max_week else course.duration_weeks
            
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
                "modules_count": modules_count,
                "created_at": course.created_at,
                "is_global": True,
                "cohort_assignments": len(cohort_assignments)
            })
        
        return {
            "courses": result,
            "total": len(result),
            "page": page,
            "limit": limit,
            "course_type": "global"
        }
    except Exception as e:
        from sqlalchemy import text
        try:
            with db.get_bind().connect() as conn:
                res = conn.execute(text("SHOW COLUMNS FROM courses"))
                cols = [r[0] for r in res]
                logger.error(f"DEBUG - Database URL: {db.get_bind().url}")
                logger.error(f"DEBUG - Actual columns in 'courses': {cols}")
        except Exception as db_err:
            logger.error(f"DEBUG - Failed to fetch columns: {db_err}")
            
        logger.error(f"Get global courses error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch global courses: {str(e)}")

@router.get("/{course_id}")
async def get_global_course_details(
    course_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get details of a global course"""
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Get assigned cohorts for information
        cohort_assignments = db.query(CohortCourse).filter(CohortCourse.course_id == course_id).all()
        
        modules = db.query(Module).filter(Module.course_id == course_id).order_by(Module.week_number).all()
        
        modules_data = []
        for module in modules:
            sessions = db.query(SessionModel).filter(SessionModel.module_id == module.id).all()
            modules_data.append({
                "id": module.id,
                "week_number": module.week_number,
                "title": module.title,
                "description": module.description,
                "start_date": module.start_date,
                "end_date": module.end_date,
                "sessions_count": len(sessions),
                "created_at": module.created_at
            })
        
        return {
            "id": course.id,
            "title": course.title,
            "description": course.description,
            "duration_weeks": course.duration_weeks,
            "sessions_per_week": course.sessions_per_week,
            "is_active": course.is_active,
            "created_at": course.created_at,
            "modules": modules_data,
            "is_global": True,
            "cohort_assignments": len(cohort_assignments),
            "payment_type": course.payment_type,
            "default_price": course.default_price,
            "assignments": [
                {
                    "assignment_type": a.assignment_type,
                    "user_id": a.user_id,
                    "college": a.college,
                    "cohort_id": a.cohort_id,
                    "assignment_mode": a.assignment_mode,
                    "amount": a.amount
                } for a in db.query(CourseAssignment).filter(CourseAssignment.course_id == course_id).all()
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get global course details error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch course details")

@router.put("/{course_id}/approval")
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
    # If approved, we can also make it active by default if it wasn't
    if new_status == 'approved':
        course.is_active = True
        
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

@router.put("/{course_id}")
async def update_global_course(
    course_id: int,
    course_data: CourseUpdate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Update a global course"""
    try:
        print(f"DEBUG: Updating course {course_id}")
        print(f"DEBUG: payload data: {course_data.dict(exclude_unset=True)}")
        
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # No need to check for cohort assignments as all courses in this table are global
        
        update_data = course_data.dict(exclude_unset=True)
        assignments_data = update_data.pop('assignments', None)
        
        print(f"DEBUG: assignments_data: {assignments_data}")

        for field, value in update_data.items():
            setattr(course, field, value)
        
        # Update Assignments if provided
        if assignments_data is not None:
            from database import CourseAssignment
            # Clear existing assignments
            print(f"DEBUG: Clearing assignments for course {course_id}")
            db.query(CourseAssignment).filter(CourseAssignment.course_id == course_id).delete()
            
            # Add new assignments
            for assignment in assignments_data:
                print(f"DEBUG: Adding assignment: {assignment}")
                new_assignment = CourseAssignment(
                    course_id=course.id,
                    assignment_type=assignment['assignment_type'],
                    user_id=assignment.get('user_id'),
                    college=assignment.get('college'),
                    cohort_id=assignment.get('cohort_id'),
                    assignment_mode=assignment.get('assignment_mode', 'free'),
                    amount=assignment.get('amount', 0.0),
                    assigned_by=current_user.id if hasattr(current_user, 'id') else None
                )
                db.add(new_assignment)
        
        db.commit()
        print("DEBUG: Commit successful")
        
        # Log course update
        from database import Admin, Presenter
        if hasattr(current_user, 'username') and db.query(Admin).filter(Admin.id == current_user.id).first():
            log_admin_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action_type="UPDATE",
                resource_type="GLOBAL_COURSE",
                resource_id=course_id,
                details=f"Updated global course: {course.title}"
            )
        elif hasattr(current_user, 'username') and db.query(Presenter).filter(Presenter.id == current_user.id).first():
            log_presenter_action(
                presenter_id=current_user.id,
                presenter_username=current_user.username,
                action_type="UPDATE",
                resource_type="GLOBAL_COURSE",
                resource_id=course_id,
                details=f"Updated global course: {course.title}"
            )
        
        return {"message": "Global course updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update global course error: {str(e)}")
        print(f"DEBUG ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update global course")

@router.delete("/{course_id}")
async def delete_global_course(
    course_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Delete a global course"""
    try:
        from database import Admin, Manager, Presenter, Mentor, User, Certificate, Resource, SessionContent, Attendance, Forum, ForumPost, Enrollment
        
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # No need to check for cohort assignments as all courses in this table are global
        
        course_title = course.title
        
        # Delete related records
        db.query(CohortCourse).filter(CohortCourse.course_id == course_id).delete()
        db.query(Enrollment).filter(Enrollment.course_id == course_id).delete()
        db.query(Certificate).filter(Certificate.course_id == course_id).delete()
        
        # Delete modules and their content
        modules = db.query(Module).filter(Module.course_id == course_id).all()
        for module in modules:
            sessions = db.query(SessionModel).filter(SessionModel.module_id == module.id).all()
            for session in sessions:
                db.query(Attendance).filter(Attendance.session_id == session.id).delete()
                db.query(Resource).filter(Resource.session_id == session.id).delete()
                db.query(SessionContent).filter(SessionContent.session_id == session.id).delete()
            
            db.query(SessionModel).filter(SessionModel.module_id == module.id).delete()
            
            forums = db.query(Forum).filter(Forum.module_id == module.id).all()
            for forum in forums:
                db.query(ForumPost).filter(ForumPost.forum_id == forum.id).delete()
            db.query(Forum).filter(Forum.module_id == module.id).delete()
        
        db.query(Module).filter(Module.course_id == course_id).delete()
        db.delete(course)
        db.commit()
        
        # Log course deletion
        from database import Admin, Presenter
        if hasattr(current_user, 'username') and db.query(Admin).filter(Admin.id == current_user.id).first():
            log_admin_action(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action_type="DELETE",
                resource_type="GLOBAL_COURSE",
                resource_id=course_id,
                details=f"Deleted global course: {course_title}"
            )
        elif hasattr(current_user, 'username') and db.query(Presenter).filter(Presenter.id == current_user.id).first():
            log_presenter_action(
                presenter_id=current_user.id,
                presenter_username=current_user.username,
                action_type="DELETE",
                resource_type="GLOBAL_COURSE",
                resource_id=course_id,
                details=f"Deleted global course: {course_title}"
            )
        
        return {"message": "Global course deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete global course error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete global course")