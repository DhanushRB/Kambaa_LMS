from fastapi import APIRouter, HTTPException, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from database import get_db, Admin, Presenter, Manager, AdminLog, PresenterLog, MentorLog, StudentLog, EmailLog, User
from resource_analytics_models import ResourceView
from auth import get_current_admin_or_presenter, verify_password, get_password_hash
from schemas import AdminCreate, PresenterCreate, ChangePasswordRequest
from utils.user_utils import check_email_exists, validate_email_zerobounce, normalize_email

import logging
import csv
import io

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin_management"])

# Assignment endpoints for admin
@router.get("/assignments")
async def get_all_assignments(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get all assignments for admin dashboard"""
    try:
        # Import models with fallback
        try:
            from assignment_quiz_models import Assignment
        except ImportError:
            from assignment_quiz_tables import Assignment
        
        from database import SessionModel, Module, Course
        from cohort_specific_models import CohortCourseSession, CohortCourseModule, CohortSpecificCourse
        
        assignments = db.query(Assignment).filter(Assignment.is_active == True).all()
        
        result = []
        for assignment in assignments:
            # Determine session type and fetch appropriate metadata
            session_type = getattr(assignment, 'session_type', 'global')
            
            if session_type == 'cohort':
                # Fetch cohort session metadata
                session = db.query(CohortCourseSession).filter(
                    CohortCourseSession.id == assignment.session_id
                ).first()
                module = db.query(CohortCourseModule).filter(
                    CohortCourseModule.id == session.module_id
                ).first() if session else None
                course = db.query(CohortSpecificCourse).filter(
                    CohortSpecificCourse.id == module.course_id
                ).first() if module else None
            else:
                # Fetch global session metadata
                session = db.query(SessionModel).filter(
                    SessionModel.id == assignment.session_id
                ).first()
                module = db.query(Module).filter(
                    Module.id == session.module_id
                ).first() if session else None
                course = db.query(Course).filter(
                    Course.id == module.course_id
                ).first() if module else None
            
            result.append({
                "id": assignment.id,
                "title": assignment.title,
                "description": assignment.description,
                "due_date": assignment.due_date,
                "total_marks": assignment.total_marks,
                "session_title": session.title if session else "Unknown",
                "module_title": module.title if module else "Unknown",
                "course_title": course.title if course else "Unknown",
                "session_type": session_type,
                "created_at": assignment.created_at
            })
        
        return {"assignments": result}
    except Exception as e:
        logger.error(f"Get assignments error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch assignments: {str(e)}")

@router.post("/assignments")
async def create_assignment(
    assignment_data: dict,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Create assignment via admin interface"""
    try:
        # Import models with fallback
        try:
            from assignment_quiz_models import Assignment, SubmissionType
        except ImportError:
            from assignment_quiz_tables import Assignment, SubmissionType
        
        from datetime import datetime
        
        # Log the received data for debugging
        logger.info(f"Received assignment data: {assignment_data}")
        
        # Handle nested data structure from frontend
        if 'course_id' in assignment_data and isinstance(assignment_data['course_id'], dict):
            assignment_data = assignment_data['course_id']
        
        # Validate required fields
        if 'session_id' not in assignment_data:
            raise HTTPException(status_code=400, detail="session_id is required")
        if 'title' not in assignment_data:
            raise HTTPException(status_code=400, detail="title is required")
        if 'due_date' not in assignment_data:
            raise HTTPException(status_code=400, detail="due_date is required")
        
        # Parse due_date
        due_date_str = assignment_data.get('due_date')
        if isinstance(due_date_str, str):
            try:
                due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
            except:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        else:
            due_date = due_date_str
        
        # Determine session type
        from cohort_specific_models import CohortCourseSession
        session_type = "global"
        cohort_session = db.query(CohortCourseSession).filter(
            CohortCourseSession.id == assignment_data['session_id']
        ).first()
        if cohort_session:
            session_type = "cohort"
        
        assignment = Assignment(
            session_id=assignment_data['session_id'],
            session_type=session_type,
            title=assignment_data['title'],
            description=assignment_data.get('description'),
            instructions=assignment_data.get('instructions'),
            submission_type=SubmissionType[assignment_data.get('submission_type', 'FILE')],
            due_date=due_date,
            total_marks=assignment_data.get('total_marks', 100),
            evaluation_criteria=assignment_data.get('evaluation_criteria'),
            created_by=current_admin.id,
            created_by_type="admin"
        )
        
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        
        return {
            "message": "Assignment created successfully",
            "assignment_id": assignment.id
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create assignment error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create assignment: {str(e)}")

@router.delete("/assignments/{assignment_id}")
async def delete_assignment(
    assignment_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Delete an assignment"""
    try:
        # Import models with fallback
        try:
            from assignment_quiz_models import Assignment, AssignmentSubmission, AssignmentGrade
        except ImportError:
            from assignment_quiz_tables import Assignment, AssignmentSubmission, AssignmentGrade
        
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Delete related submissions and grades
        submissions = db.query(AssignmentSubmission).filter(
            AssignmentSubmission.assignment_id == assignment_id
        ).all()
        
        for submission in submissions:
            db.query(AssignmentGrade).filter(
                AssignmentGrade.submission_id == submission.id
            ).delete()
        
        db.query(AssignmentSubmission).filter(
            AssignmentSubmission.assignment_id == assignment_id
        ).delete()
        
        db.delete(assignment)
        db.commit()
        
        return {"message": "Assignment deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete assignment error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete assignment: {str(e)}")

@router.get("/quizzes")
async def get_all_quizzes(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get all quizzes for admin dashboard"""
    try:
        from assignment_quiz_models import Quiz
        from database import SessionModel, Module, Course
        
        quizzes = db.query(Quiz).filter(Quiz.is_active == True).all()
        
        result = []
        for quiz in quizzes:
            # Get session, module, and course info
            session = db.query(SessionModel).filter(SessionModel.id == quiz.session_id).first()
            module = db.query(Module).filter(Module.id == session.module_id).first() if session else None
            course = db.query(Course).filter(Course.id == module.course_id).first() if module else None
            
            result.append({
                "id": quiz.id,
                "title": quiz.title,
                "description": quiz.description,
                "time_limit_minutes": quiz.time_limit_minutes,
                "total_marks": quiz.total_marks,
                "session_title": session.title if session else "Unknown",
                "module_title": module.title if module else "Unknown",
                "course_title": course.title if course else "Unknown",
                "created_at": quiz.created_at
            })
        
        return {"quizzes": result}
    except Exception as e:
        logger.error(f"Get quizzes error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch quizzes: {str(e)}")

@router.post("/create-admin")
async def create_admin(
    admin_data: AdminCreate,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        normalized_email = normalize_email(admin_data.email)
        
        # Unified duplicate check
        db_check = check_email_exists(normalized_email, db)
        if db_check["exists"]:
            raise HTTPException(status_code=400, detail=f"Email already exists (Role: {db_check['role']})")
        
        # ZeroBounce validation
        zb_check = validate_email_zerobounce(normalized_email)
        if not zb_check["valid"]:
            raise HTTPException(status_code=400, detail=f"Email validation failed: {zb_check['message']}")

        if db.query(Admin).filter(Admin.username == admin_data.username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        hashed_password = get_password_hash(admin_data.password)
        admin = Admin(
            username=admin_data.username,
            email=admin_data.email,
            password_hash=hashed_password
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        return {"message": "Admin created successfully", "admin_id": admin.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create admin error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create admin")

@router.post("/create-presenter")
async def create_presenter(
    presenter_data: PresenterCreate,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        normalized_email = normalize_email(presenter_data.email)
        
        # Unified duplicate check
        db_check = check_email_exists(normalized_email, db)
        if db_check["exists"]:
            raise HTTPException(status_code=400, detail=f"Email already exists (Role: {db_check['role']})")
        
        # ZeroBounce validation
        zb_check = validate_email_zerobounce(normalized_email)
        if not zb_check["valid"]:
            raise HTTPException(status_code=400, detail=f"Email validation failed: {zb_check['message']}")

        if db.query(Presenter).filter(Presenter.username == presenter_data.username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        hashed_password = get_password_hash(presenter_data.password)
        presenter = Presenter(
            username=presenter_data.username,
            email=presenter_data.email,
            password_hash=hashed_password
        )
        db.add(presenter)
        db.commit()
        db.refresh(presenter)
        
        return {"message": "Presenter created successfully", "presenter_id": presenter.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create presenter error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create presenter")

@router.post("/create-manager")
async def create_manager(
    manager_data: AdminCreate,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        normalized_email = normalize_email(manager_data.email)
        
        # Unified duplicate check
        db_check = check_email_exists(normalized_email, db)
        if db_check["exists"]:
            raise HTTPException(status_code=400, detail=f"Email already exists (Role: {db_check['role']})")
        
        # ZeroBounce validation
        zb_check = validate_email_zerobounce(normalized_email)
        if not zb_check["valid"]:
            raise HTTPException(status_code=400, detail=f"Email validation failed: {zb_check['message']}")

        if db.query(Manager).filter(Manager.username == manager_data.username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        hashed_password = get_password_hash(manager_data.password)
        manager = Manager(
            username=manager_data.username,
            email=manager_data.email,
            password_hash=hashed_password
        )
        db.add(manager)
        db.commit()
        db.refresh(manager)
        
        return {"message": "Manager created successfully", "manager_id": manager.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create manager error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create manager")

@router.get("/presenters")
async def get_all_presenters(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        presenters = db.query(Presenter).all()
        
        return {
            "presenters": [{
                "id": p.id,
                "username": p.username,
                "email": p.email,
                "is_active": getattr(p, 'is_active', True),
                "created_at": p.created_at
            } for p in presenters]
        }
    except Exception as e:
        logger.error(f"Get presenters error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch presenters")

@router.post("/change-password")
async def change_admin_password(
    password_data: ChangePasswordRequest,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        if not verify_password(password_data.current_password, current_admin.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        
        current_admin.password_hash = get_password_hash(password_data.new_password)
        db.commit()
        
        return {"message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Change password error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to change password")

@router.post("/presenter-logs")
async def get_presenter_logs(
    filters: dict,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get presenter logs for admin activity logs page"""
    try:
        query = db.query(PresenterLog)
        
        if filters.get('action_type'):
            query = query.filter(PresenterLog.action_type == filters['action_type'])
        
        if filters.get('resource_type'):
            query = query.filter(PresenterLog.resource_type == filters['resource_type'])
        
        if filters.get('date_from'):
            query = query.filter(PresenterLog.timestamp >= filters['date_from'])
        
        if filters.get('date_to'):
            query = query.filter(PresenterLog.timestamp <= filters['date_to'])
        
        if filters.get('search'):
            query = query.filter(
                or_(
                    PresenterLog.presenter_username.contains(filters['search']),
                    PresenterLog.details.contains(filters['search'])
                )
            )
        
        page = filters.get('page', 1)
        limit = 50
        logs = query.order_by(PresenterLog.timestamp.desc()).offset((page - 1) * limit).limit(limit).all()
        
        logs_data = []
        for log in logs:
            logs_data.append({
                "id": log.id,
                "presenter_id": log.presenter_id,
                "presenter_username": log.presenter_username,
                "action_type": log.action_type,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else None
            })
        
        return {"logs": logs_data}
    except Exception as e:
        logger.error(f"Get presenter logs error: {str(e)}")
        return {"logs": []}

@router.get("/test-logs")
async def test_logs(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Test endpoint to check if logs exist"""
    try:
        admin_count = db.query(AdminLog).count()
        presenter_count = db.query(PresenterLog).count()
        
        admin_logs = db.query(AdminLog).order_by(AdminLog.timestamp.desc()).limit(3).all()
        presenter_logs = db.query(PresenterLog).order_by(PresenterLog.timestamp.desc()).limit(3).all()
        
        return {
            "admin_count": admin_count,
            "presenter_count": presenter_count,
            "sample_admin_logs": [{
                "id": log.id,
                "username": log.admin_username,
                "action": log.action_type,
                "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else None
            } for log in admin_logs],
            "sample_presenter_logs": [{
                "id": log.id,
                "username": log.presenter_username,
                "action": log.action_type,
                "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else None
            } for log in presenter_logs]
        }
    except Exception as e:
        logger.error(f"Test logs error: {str(e)}")
        return {"error": str(e)}

@router.get("/logs")
async def get_admin_logs(
    page: int = 1,
    limit: int = 50,
    action_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get admin logs with filtering"""
    return await get_all_system_logs(
        page=page,
        limit=limit,
        action_type=action_type,
        resource_type=resource_type,
        user_type=None,
        date_from=date_from,
        date_to=date_to,
        search=search,
        current_admin=current_admin,
        db=db
    )

@router.get("/logs/all")
async def get_all_system_logs(
    page: int = 1,
    limit: int = 50,
    action_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    user_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get all system logs from all user types"""
    try:
        all_logs = []
        
        # Get admin logs
        admin_query = db.query(AdminLog)
        if action_type:
            admin_query = admin_query.filter(AdminLog.action_type == action_type)
        if resource_type:
            admin_query = admin_query.filter(AdminLog.resource_type == resource_type)
        if date_from:
            admin_query = admin_query.filter(AdminLog.timestamp >= date_from)
        if date_to:
            admin_query = admin_query.filter(AdminLog.timestamp <= date_to)
        if search:
            admin_query = admin_query.filter(
                or_(
                    AdminLog.admin_username.contains(search),
                    AdminLog.details.contains(search)
                )
            )
        
        if not user_type or user_type == "Admin":
            admin_logs = admin_query.all()
            for log in admin_logs:
                all_logs.append({
                    "id": f"admin_{log.id}",
                    "user_type": "Admin",
                    "user_id": log.admin_id,
                    "username": log.admin_username,
                    "action_type": log.action_type,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "details": log.details,
                    "ip_address": log.ip_address,
                    "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else None
                })
        
        # Get presenter logs
        presenter_query = db.query(PresenterLog)
        if action_type:
            presenter_query = presenter_query.filter(PresenterLog.action_type == action_type)
        if resource_type:
            presenter_query = presenter_query.filter(PresenterLog.resource_type == resource_type)
        if date_from:
            presenter_query = presenter_query.filter(PresenterLog.timestamp >= date_from)
        if date_to:
            presenter_query = presenter_query.filter(PresenterLog.timestamp <= date_to)
        if search:
            presenter_query = presenter_query.filter(
                or_(
                    PresenterLog.presenter_username.contains(search),
                    PresenterLog.details.contains(search)
                )
            )
        
        if not user_type or user_type == "Presenter":
            presenter_logs = presenter_query.all()
            for log in presenter_logs:
                all_logs.append({
                    "id": f"presenter_{log.id}",
                    "user_type": "Presenter",
                    "user_id": log.presenter_id,
                    "username": log.presenter_username,
                    "action_type": log.action_type,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "details": log.details,
                    "ip_address": log.ip_address,
                    "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else None
                })
        
        # Get mentor logs
        mentor_query = db.query(MentorLog)
        if action_type:
            mentor_query = mentor_query.filter(MentorLog.action_type == action_type)
        if resource_type:
            mentor_query = mentor_query.filter(MentorLog.resource_type == resource_type)
        if date_from:
            mentor_query = mentor_query.filter(MentorLog.timestamp >= date_from)
        if date_to:
            mentor_query = mentor_query.filter(MentorLog.timestamp <= date_to)
        if search:
            mentor_query = mentor_query.filter(
                or_(
                    MentorLog.mentor_username.contains(search),
                    MentorLog.details.contains(search)
                )
            )
        
        if not user_type or user_type == "Mentor":
            mentor_logs = mentor_query.all()
            for log in mentor_logs:
                all_logs.append({
                    "id": f"mentor_{log.id}",
                    "user_type": "Mentor",
                    "user_id": log.mentor_id,
                    "username": log.mentor_username,
                    "action_type": log.action_type,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "details": log.details,
                    "ip_address": log.ip_address,
                    "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else None
                })
        
        # Get student logs
        student_query = db.query(StudentLog)
        if action_type:
            student_query = student_query.filter(StudentLog.action_type == action_type)
        if resource_type:
            student_query = student_query.filter(StudentLog.resource_type == resource_type)
        if date_from:
            student_query = student_query.filter(StudentLog.timestamp >= date_from)
        if date_to:
            student_query = student_query.filter(StudentLog.timestamp <= date_to)
        if search:
            student_query = student_query.filter(
                or_(
                    StudentLog.student_username.contains(search),
                    StudentLog.details.contains(search)
                )
            )
        
        if not user_type or user_type == "Student":
            student_logs = student_query.all()
            for log in student_logs:
                all_logs.append({
                    "id": f"student_{log.id}",
                    "user_type": "Student",
                    "user_id": log.student_id,
                    "username": log.student_username,
                    "action_type": log.action_type,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "details": log.details,
                    "ip_address": log.ip_address,
                    "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else None
                })
        
        # Get email logs
        email_query = db.query(EmailLog)
        if date_from:
            email_query = email_query.filter(EmailLog.created_at >= date_from)
        if date_to:
            email_query = email_query.filter(EmailLog.created_at <= date_to)
        if search:
            email_query = email_query.filter(
                or_(
                    EmailLog.email.contains(search),
                    EmailLog.subject.contains(search),
                    EmailLog.status.contains(search)
                )
            )
            
        if not user_type or user_type == "System":
            email_logs = email_query.all()
            for log in email_logs:
                all_logs.append({
                    "id": f"email_{log.id}",
                    "user_type": "System",
                    "user_id": log.user_id,
                    "username": log.email,
                    "action_type": "EMAIL_SENT" if log.status == "sent" else "EMAIL_FAILED",
                    "resource_type": "EMAIL",
                    "resource_id": log.id,
                    "details": f"Subject: {log.subject} (Status: {log.status})",
                    "ip_address": None,
                    "timestamp": log.created_at.isoformat() + "Z" if log.created_at else None
                })

        # Get resource view logs (Student activity)
        view_query = db.query(ResourceView)
        if date_from:
            view_query = view_query.filter(ResourceView.viewed_at >= date_from)
        if date_to:
            view_query = view_query.filter(ResourceView.viewed_at <= date_to)
        if search:
            # We need to join with User to search by username
            view_query = view_query.join(User, ResourceView.student_id == User.id).filter(
                or_(
                    User.username.contains(search),
                    ResourceView.resource_type.contains(search)
                )
            )
        
        if not user_type or user_type == "Student":
            # Avoid duplicate student logs if user_type is Student, 
            # but ResourceView is a different kind of activity.
            # I'll label them as UserType: Student, Action: VIEW
            view_logs = view_query.all()
            for log in view_logs:
                # Get username for the log
                user_obj = db.query(User).filter(User.id == log.student_id).first()
                all_logs.append({
                    "id": f"view_{log.id}",
                    "user_type": "Student",
                    "user_id": log.student_id,
                    "username": user_obj.username if user_obj else f"User {log.student_id}",
                    "action_type": "VIEW",
                    "resource_type": log.resource_type or "RESOURCE",
                    "resource_id": log.resource_id,
                    "details": f"Viewed {log.resource_type or 'resource'} (ID: {log.resource_id})",
                    "ip_address": log.ip_address,
                    "timestamp": log.viewed_at.isoformat() + "Z" if log.viewed_at else None
                })
        
        # Sort by timestamp (most recent first)
        all_logs.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Apply pagination
        total = len(all_logs)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_logs = all_logs[start_idx:end_idx]
        
        return {
            "data": {
                "logs": paginated_logs,
                "total": total,
                "page": page,
                "limit": limit
            }
        }
    except Exception as e:
        logger.error(f"Get all system logs error: {str(e)}")
        return {"data": {"logs": [], "total": 0, "page": page, "limit": limit}}

@router.get("/logs/export")
async def export_all_logs(
    action_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    user_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Export all system logs as CSV"""
    try:
        all_logs = []
        
        # Get admin logs
        admin_query = db.query(AdminLog)
        if action_type:
            admin_query = admin_query.filter(AdminLog.action_type == action_type)
        if resource_type:
            admin_query = admin_query.filter(AdminLog.resource_type == resource_type)
        if date_from:
            admin_query = admin_query.filter(AdminLog.timestamp >= date_from)
        if date_to:
            admin_query = admin_query.filter(AdminLog.timestamp <= date_to)
        if search:
            admin_query = admin_query.filter(
                or_(
                    AdminLog.admin_username.contains(search),
                    AdminLog.details.contains(search)
                )
            )
        
        if not user_type or user_type == "Admin":
            admin_logs = admin_query.all()
            for log in admin_logs:
                all_logs.append({
                    "id": f"admin_{log.id}",
                    "user_type": "Admin",
                    "user_id": log.admin_id,
                    "username": log.admin_username,
                    "action_type": log.action_type,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "details": log.details,
                    "ip_address": log.ip_address,
                    "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else None
                })
        
        # Get presenter logs
        presenter_query = db.query(PresenterLog)
        if action_type:
            presenter_query = presenter_query.filter(PresenterLog.action_type == action_type)
        if resource_type:
            presenter_query = presenter_query.filter(PresenterLog.resource_type == resource_type)
        if date_from:
            presenter_query = presenter_query.filter(PresenterLog.timestamp >= date_from)
        if date_to:
            presenter_query = presenter_query.filter(PresenterLog.timestamp <= date_to)
        if search:
            presenter_query = presenter_query.filter(
                or_(
                    PresenterLog.presenter_username.contains(search),
                    PresenterLog.details.contains(search)
                )
            )
        
        if not user_type or user_type == "Presenter":
            presenter_logs = presenter_query.all()
            for log in presenter_logs:
                all_logs.append({
                    "id": f"presenter_{log.id}",
                    "user_type": "Presenter",
                    "user_id": log.presenter_id,
                    "username": log.presenter_username,
                    "action_type": log.action_type,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "details": log.details,
                    "ip_address": log.ip_address,
                    "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else None
                })
        
        # Get mentor logs
        mentor_query = db.query(MentorLog)
        if action_type:
            mentor_query = mentor_query.filter(MentorLog.action_type == action_type)
        if resource_type:
            mentor_query = mentor_query.filter(MentorLog.resource_type == resource_type)
        if date_from:
            mentor_query = mentor_query.filter(MentorLog.timestamp >= date_from)
        if date_to:
            mentor_query = mentor_query.filter(MentorLog.timestamp <= date_to)
        if search:
            mentor_query = mentor_query.filter(
                or_(
                    MentorLog.mentor_username.contains(search),
                    MentorLog.details.contains(search)
                )
            )
        
        if not user_type or user_type == "Mentor":
            mentor_logs = mentor_query.all()
            for log in mentor_logs:
                all_logs.append({
                    "id": f"mentor_{log.id}",
                    "user_type": "Mentor",
                    "user_id": log.mentor_id,
                    "username": log.mentor_username,
                    "action_type": log.action_type,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "details": log.details,
                    "ip_address": log.ip_address,
                    "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else None
                })
        
        # Get student logs
        student_query = db.query(StudentLog)
        if action_type:
            student_query = student_query.filter(StudentLog.action_type == action_type)
        if resource_type:
            student_query = student_query.filter(StudentLog.resource_type == resource_type)
        if date_from:
            student_query = student_query.filter(StudentLog.timestamp >= date_from)
        if date_to:
            student_query = student_query.filter(StudentLog.timestamp <= date_to)
        if search:
            student_query = student_query.filter(
                or_(
                    StudentLog.student_username.contains(search),
                    StudentLog.details.contains(search)
                )
            )
        
        if not user_type or user_type == "Student":
            student_logs = student_query.all()
            for log in student_logs:
                all_logs.append({
                    "id": f"student_{log.id}",
                    "user_type": "Student",
                    "user_id": log.student_id,
                    "username": log.student_username,
                    "action_type": log.action_type,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "details": log.details,
                    "ip_address": log.ip_address,
                    "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else None
                })
        
        # Sort by timestamp (most recent first)
        all_logs.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Timestamp', 'User Type', 'Username', 'Action', 'Resource Type', 'Resource ID', 'Details'])
        
        # Write data
        for log in all_logs:
            writer.writerow([
                log['timestamp'],
                log['user_type'],
                log['username'],
                log['action_type'],
                log['resource_type'],
                log['resource_id'],
                log['details']
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "inline; filename=system_activity_logs.csv"}
        )
    except Exception as e:
        logger.error(f"Export logs error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export logs")

@router.get("/github-stats")
async def get_github_stats(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get GitHub link submission statistics"""
    try:
        from database import User
        
        # Count total students (users with role='Student')
        total_students = db.query(User).filter(User.role == "Student").count()
        
        # Count students with GitHub links (non-null and non-empty)
        students_with_github = db.query(User).filter(
            User.role == "Student",
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
        logger.error(f"Get GitHub stats error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch GitHub statistics")