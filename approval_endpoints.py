from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
import json

from database import get_db, User, Admin, Presenter, Mentor, Manager, Course, Module, Session as SessionModel, Resource, SessionContent
from auth import get_current_admin_or_presenter, get_current_user, get_current_presenter, get_current_mentor, verify_token
from approval_models import ApprovalRequest, EntityStatus, ApprovalStatus, OperationType

router = APIRouter(prefix="/approvals", tags=["approvals"])

# Function to execute approved operations
async def execute_approved_operation(
    approval_request: ApprovalRequest, 
    db: Session,
    payment_type: Optional[str] = None,
    default_price: Optional[float] = None
):
    """Execute the actual operation after approval is granted"""
    operation_type = approval_request.operation_type
    target_entity_type = approval_request.target_entity_type
    target_entity_id = approval_request.target_entity_id
    
    if operation_type == OperationType.DELETE:
        if target_entity_type == "course":
            course = db.query(Course).filter(Course.id == target_entity_id).first()
            if course:
                # Delete related records first to avoid foreign key constraints
                from database import CohortCourse, Enrollment, Certificate, Attendance, Forum, ForumPost
                from assignment_quiz_models import Assignment, AssignmentSubmission as Submission, Quiz, QuizAttempt
                
                # Delete cohort_courses entries
                db.query(CohortCourse).filter(CohortCourse.course_id == target_entity_id).delete()
                
                # Delete enrollments
                db.query(Enrollment).filter(Enrollment.course_id == target_entity_id).delete()
                
                # Assignments are removed per-session below
                
                # Delete certificates
                db.query(Certificate).filter(Certificate.course_id == target_entity_id).delete()
                
                # Delete modules and their related content
                modules = db.query(Module).filter(Module.course_id == target_entity_id).all()
                for module in modules:
                    # Get sessions for this module
                    sessions = db.query(SessionModel).filter(SessionModel.module_id == module.id).all()
                    for session in sessions:
                        # Delete session-related content
                        db.query(Attendance).filter(Attendance.session_id == session.id).delete()
                        db.query(Resource).filter(Resource.session_id == session.id).delete()
                        db.query(SessionContent).filter(SessionContent.session_id == session.id).delete()
                        
                        # Delete quizzes and their attempts
                        quizzes = db.query(Quiz).filter(Quiz.session_id == session.id).all()
                        for quiz in quizzes:
                            db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz.id).delete()
                        db.query(Quiz).filter(Quiz.session_id == session.id).delete()
                        from assignment_quiz_models import Assignment, AssignmentSubmission as Submission, AssignmentGrade
                        assignments = db.query(Assignment).filter(Assignment.session_id == session.id).all()
                        for a in assignments:
                            db.query(AssignmentGrade).filter(AssignmentGrade.assignment_id == a.id).delete()
                            db.query(Submission).filter(Submission.assignment_id == a.id).delete()
                        db.query(Assignment).filter(Assignment.session_id == session.id).delete()
                    
                    # Delete sessions
                    db.query(SessionModel).filter(SessionModel.module_id == module.id).delete()
                    
                    # Delete forums and their posts
                    forums = db.query(Forum).filter(Forum.module_id == module.id).all()
                    for forum in forums:
                        db.query(ForumPost).filter(ForumPost.forum_id == forum.id).delete()
                    db.query(Forum).filter(Forum.module_id == module.id).delete()
                
                # Delete modules
                db.query(Module).filter(Module.course_id == target_entity_id).delete()
                
                # Finally delete the course
                db.delete(course)
                
        elif target_entity_type == "module":
            module = db.query(Module).filter(Module.id == target_entity_id).first()
            if module:
                # Delete related sessions and content
                sessions = db.query(SessionModel).filter(SessionModel.module_id == target_entity_id).all()
                for session in sessions:
                    db.query(Attendance).filter(Attendance.session_id == session.id).delete()
                    db.query(Resource).filter(Resource.session_id == session.id).delete()
                    db.query(SessionContent).filter(SessionContent.session_id == session.id).delete()
                    
                    from assignment_quiz_models import Quiz, QuizAttempt
                    quizzes = db.query(Quiz).filter(Quiz.session_id == session.id).all()
                    for quiz in quizzes:
                        db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz.id).delete()
                    db.query(Quiz).filter(Quiz.session_id == session.id).delete()
                    from assignment_quiz_models import Assignment, AssignmentSubmission as Submission, AssignmentGrade
                    assignments = db.query(Assignment).filter(Assignment.session_id == session.id).all()
                    for a in assignments:
                        db.query(AssignmentGrade).filter(AssignmentGrade.assignment_id == a.id).delete()
                        db.query(Submission).filter(Submission.assignment_id == a.id).delete()
                    db.query(Assignment).filter(Assignment.session_id == session.id).delete()
                
                db.query(SessionModel).filter(SessionModel.module_id == target_entity_id).delete()
                db.delete(module)
                
        elif target_entity_type == "session":
            session = db.query(SessionModel).filter(SessionModel.id == target_entity_id).first()
            if session:
                # Delete related content
                db.query(Attendance).filter(Attendance.session_id == target_entity_id).delete()
                db.query(Resource).filter(Resource.session_id == target_entity_id).delete()
                db.query(SessionContent).filter(SessionContent.session_id == target_entity_id).delete()
                
                from assignment_quiz_models import Quiz, QuizAttempt
                quizzes = db.query(Quiz).filter(Quiz.session_id == target_entity_id).all()
                for quiz in quizzes:
                    db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz.id).delete()
                db.query(Quiz).filter(Quiz.session_id == target_entity_id).delete()
                from assignment_quiz_models import Assignment, AssignmentSubmission as Submission, AssignmentGrade
                assignments = db.query(Assignment).filter(Assignment.session_id == target_entity_id).all()
                for a in assignments:
                    db.query(AssignmentGrade).filter(AssignmentGrade.assignment_id == a.id).delete()
                    db.query(Submission).filter(Submission.assignment_id == a.id).delete()
                db.query(Assignment).filter(Assignment.session_id == target_entity_id).delete()
                
                db.delete(session)
                
        elif target_entity_type == "resource":
            resource = db.query(Resource).filter(Resource.id == target_entity_id).first()
            if resource:
                # Delete physical file if exists
                import os
                if resource.file_path and os.path.exists(resource.file_path):
                    os.remove(resource.file_path)
                db.delete(resource)
            else:
                # Try SessionContent table
                session_content = db.query(SessionContent).filter(SessionContent.id == target_entity_id).first()
                if session_content:
                    # Delete physical file if exists (but not for meeting links)
                    import os
                    if session_content.file_path and os.path.exists(session_content.file_path) and session_content.content_type != "MEETING_LINK":
                        os.remove(session_content.file_path)
                    db.delete(session_content)
    
    # Add other operation types as needed (UPDATE, DISABLE, etc.)
    elif operation_type == OperationType.DISABLE:
        # Handle disable operations
        if target_entity_type == "course":
            course = db.query(Course).filter(Course.id == target_entity_id).first()
            if course and hasattr(course, 'is_active'):
                course.is_active = False
                
    elif operation_type == OperationType.UNPUBLISH:
        # Handle unpublish operations
        if target_entity_type == "course":
            course = db.query(Course).filter(Course.id == target_entity_id).first()
            if course and hasattr(course, 'is_published'):
                course.is_published = False

    elif operation_type == OperationType.CREATE:
        if target_entity_type == "course":
            course = db.query(Course).filter(Course.id == target_entity_id).first()
            if course:
                course.approval_status = 'approved'
                course.is_active = True
                if payment_type:
                    course.payment_type = payment_type
                if default_price is not None:
                    course.default_price = default_price
                logger.info(f"Course {target_entity_id} approved and activated with payment_type={payment_type}, price={default_price}")

# Request models
class ApprovalDecisionRequest(BaseModel):
    decision: str
    rejection_reason: Optional[str] = None
    payment_type: Optional[str] = None
    default_price: Optional[float] = None

class ApprovalRequestCreate(BaseModel):
    operation_type: str
    target_entity_type: str
    target_entity_id: int
    operation_data: dict = {}
    reason: Optional[str] = None

# Create approval request
@router.post("/request")
async def create_approval_request(
    req: ApprovalRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if user can request approvals (Student, Presenter, Mentor)
    if current_user.role not in ["Student", "Presenter", "Mentor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Students, Presenters, and Mentors can request approvals"
        )
    
    # Create approval request
    try:
        op_type = OperationType(req.operation_type)
    except Exception:
        # Try case-insensitive match
        try:
            op_type = OperationType[req.operation_type.upper()]
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid operation_type")

    approval_request = ApprovalRequest(
        requester_id=current_user.id,
        operation_type=op_type,
        target_entity_type=req.target_entity_type,
        target_entity_id=req.target_entity_id,
        operation_data=json.dumps(req.operation_data or {}),
        reason=req.reason,
        status=ApprovalStatus.PENDING
    )
    
    db.add(approval_request)
    db.commit()
    db.refresh(approval_request)
    
    # Update entity status to pending approval
    entity_status = db.query(EntityStatus).filter(
        EntityStatus.entity_type == req.target_entity_type,
        EntityStatus.entity_id == req.target_entity_id
    ).first()
    
    if entity_status:
        entity_status.status = "pending_approval"
        entity_status.approval_request_id = approval_request.id
    else:
        entity_status = EntityStatus(
            entity_type=req.target_entity_type,
            entity_id=req.target_entity_id,
            status="pending_approval",
            approval_request_id=approval_request.id
        )
        db.add(entity_status)
    
    db.commit()
    
    return {
        "message": "Approval request created successfully",
        "request_id": approval_request.id,
        "icon": "request",
        "status": "pending"
    }

# Get pending approval requests (Admin/Manager only)
@router.get("/pending")
async def get_pending_approvals(
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    # Check if user can approve requests (Admin, Manager)
    # Role check is handled by get_current_admin_or_presenter dependency
    
    requests = db.query(ApprovalRequest).filter(
        ApprovalRequest.status == ApprovalStatus.PENDING
    ).all()
    
    result = []
    for req in requests:
        # Manually fetch requester information since there's no FK relationship
        requester = None
        requester_name = "Unknown"
        requester_role = "Unknown"
        
        # Try to find the requester in different tables
        from database import User, Admin, Presenter, Mentor, Manager
        
        # Check User table first
        user_check = db.query(User).filter(User.id == req.requester_id).first()
        if user_check:
            requester_name = user_check.username
            requester_role = user_check.role
        else:
            # Check Admin table
            admin_check = db.query(Admin).filter(Admin.id == req.requester_id).first()
            if admin_check:
                requester_name = admin_check.username
                requester_role = "Admin"
            else:
                # Check Presenter table
                presenter_check = db.query(Presenter).filter(Presenter.id == req.requester_id).first()
                if presenter_check:
                    requester_name = presenter_check.username
                    requester_role = "Presenter"
                else:
                    # Check Mentor table
                    mentor_check = db.query(Mentor).filter(Mentor.id == req.requester_id).first()
                    if mentor_check:
                        requester_name = mentor_check.username
                        requester_role = "Mentor"
                    else:
                        # Check Manager table
                        manager_check = db.query(Manager).filter(Manager.id == req.requester_id).first()
                        if manager_check:
                            requester_name = manager_check.username
                            requester_role = "Manager"
        
        # Get icon based on operation type
        icon = "request"
        if req.operation_type == OperationType.DELETE:
            icon = "delete"
        elif req.operation_type == OperationType.DISABLE:
            icon = "disable"
        elif req.operation_type == OperationType.UNPUBLISH:
            icon = "unpublish"
        
        result.append({
            "id": req.id,
            "requester": {
                "id": req.requester_id,
                "name": requester_name,
                "role": requester_role
            },
            "operation_type": req.operation_type.value if hasattr(req.operation_type, 'value') else req.operation_type,
            "target_entity_type": req.target_entity_type,
            "target_entity_id": req.target_entity_id,
            "operation_data": json.loads(req.operation_data) if req.operation_data else {},
            "reason": req.reason,
            "created_at": req.created_at.isoformat(),
            "status": req.status.value,
            "icon": icon
        })
    
    return {"requests": result}

# Approve or reject request
@router.post("/{request_id}/decision")
async def make_approval_decision(
    request_id: int,
    request_data: ApprovalDecisionRequest,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    # Check if user can approve requests (Admin, Manager)
    # Role check is handled by get_current_admin_or_presenter dependency
    
    if request_data.decision not in ["approve", "reject"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision must be 'approve' or 'reject'"
        )
    
    # Get approval request
    approval_request = db.query(ApprovalRequest).filter(
        ApprovalRequest.id == request_id,
        ApprovalRequest.status == ApprovalStatus.PENDING
    ).first()
    
    if not approval_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval request not found or already processed"
        )
    
    # Update approval request
    if request_data.decision == "approve":
        approval_request.status = ApprovalStatus.APPROVED
        approved_by_id = getattr(current_user, 'id', None)
        if approved_by_id is None and isinstance(current_user, dict):
            approved_by_id = current_user.get('id')
        if approved_by_id is None:
            raise HTTPException(status_code=401, detail="Invalid approver")
        approval_request.approved_by = approved_by_id
        approval_request.approved_at = datetime.utcnow()
        
        # Execute the requested operation here
        try:
            await execute_approved_operation(
                approval_request, 
                db, 
                payment_type=request_data.payment_type, 
                default_price=request_data.default_price
            )
        except Exception as e:
            # If operation fails, revert approval status
            approval_request.status = ApprovalStatus.PENDING
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to execute approved operation: {str(e)}"
            )
        
        # Update entity status back to active (or remove if deleted)
        entity_status = db.query(EntityStatus).filter(
            EntityStatus.approval_request_id == request_id
        ).first()
        if entity_status:
            if approval_request.operation_type == OperationType.DELETE:
                # Remove entity status for deleted items
                db.delete(entity_status)
            else:
                entity_status.status = "active"
        
    else:  # reject
        approval_request.status = ApprovalStatus.REJECTED
        approved_by_id = getattr(current_user, 'id', None)
        if approved_by_id is None and isinstance(current_user, dict):
            approved_by_id = current_user.get('id')
        if approved_by_id is None:
            raise HTTPException(status_code=401, detail="Invalid approver")
        approval_request.approved_by = approved_by_id
        approval_request.approved_at = datetime.utcnow()
        approval_request.rejection_reason = request_data.rejection_reason
        
        # Restore entity to previous active state
        entity_status = db.query(EntityStatus).filter(
            EntityStatus.approval_request_id == request_id
        ).first()
        if entity_status:
            entity_status.status = "active"
    
    db.commit()
    
    decision_icon = "approved" if request_data.decision == "approve" else "rejected"
    return {
        "message": f"Request {request_data.decision}d successfully",
        "icon": decision_icon,
        "status": request_data.decision + "d"
    }

# Get user's approval requests (for any authenticated user)
@router.get("/my-requests")
async def get_my_approval_requests(
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    requests = db.query(ApprovalRequest).filter(
        ApprovalRequest.requester_id == current_user.id
    ).order_by(ApprovalRequest.created_at.desc()).all()
    
    result = []
    for req in requests:
        approver_name = None
        if req.approver:
            approver_name = req.approver.full_name or req.approver.username
        
        # Get icon based on status and operation type
        if req.status == ApprovalStatus.APPROVED:
            icon = "approved"
        elif req.status == ApprovalStatus.REJECTED:
            icon = "rejected"
        elif req.operation_type == OperationType.DELETE:
            icon = "delete"
        elif req.operation_type == OperationType.DISABLE:
            icon = "disable"
        elif req.operation_type == OperationType.UNPUBLISH:
            icon = "unpublish"
        else:
            icon = "pending"
        
        result.append({
            "id": req.id,
            "operation_type": req.operation_type.value if hasattr(req.operation_type, 'value') else req.operation_type,
            "target_entity_type": req.target_entity_type,
            "target_entity_id": req.target_entity_id,
            "reason": req.reason,
            "status": req.status.value,
            "approver": approver_name,
            "approved_at": req.approved_at.isoformat() if req.approved_at else None,
            "rejection_reason": req.rejection_reason,
            "created_at": req.created_at.isoformat(),
            "icon": icon
        })
    
    return {"requests": result}

# Get presenter's approval requests (for presenter dashboard)
@router.get("/presenter/my-requests")
async def get_presenter_approval_requests(
    current_presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    requests = db.query(ApprovalRequest).filter(
        ApprovalRequest.requester_id == current_presenter.id
    ).order_by(ApprovalRequest.created_at.desc()).all()
    
    result = []
    for req in requests:
        # Get approver name
        approver_name = None
        if req.approved_by:
            admin_check = db.query(Admin).filter(Admin.id == req.approved_by).first()
            if admin_check:
                approver_name = admin_check.username
            else:
                manager_check = db.query(Manager).filter(Manager.id == req.approved_by).first()
                if manager_check:
                    approver_name = manager_check.username
        
        # Get icon based on status and operation type
        if req.status == ApprovalStatus.APPROVED:
            icon = "approved"
        elif req.status == ApprovalStatus.REJECTED:
            icon = "rejected"
        elif req.operation_type == OperationType.DELETE:
            icon = "delete"
        elif req.operation_type == OperationType.DISABLE:
            icon = "disable"
        elif req.operation_type == OperationType.UNPUBLISH:
            icon = "unpublish"
        else:
            icon = "pending"
        
        result.append({
            "id": req.id,
            "operation_type": req.operation_type.value if hasattr(req.operation_type, 'value') else req.operation_type,
            "target_entity_type": req.target_entity_type,
            "target_entity_id": req.target_entity_id,
            "reason": req.reason,
            "status": req.status.value,
            "approver": approver_name,
            "approved_at": req.approved_at.isoformat() if req.approved_at else None,
            "rejection_reason": req.rejection_reason,
            "created_at": req.created_at.isoformat(),
            "icon": icon
        })
    
    return {"requests": result}

# Get mentor's approval requests (for mentor dashboard)
@router.get("/mentor/my-requests")
async def get_mentor_approval_requests(
    current_mentor = Depends(get_current_mentor),
    db: Session = Depends(get_db)
):
    requests = db.query(ApprovalRequest).filter(
        ApprovalRequest.requester_id == current_mentor.id
    ).order_by(ApprovalRequest.created_at.desc()).all()
    
    result = []
    for req in requests:
        # Get approver name
        approver_name = None
        if req.approved_by:
            admin_check = db.query(Admin).filter(Admin.id == req.approved_by).first()
            if admin_check:
                approver_name = admin_check.username
            else:
                manager_check = db.query(Manager).filter(Manager.id == req.approved_by).first()
                if manager_check:
                    approver_name = manager_check.username
        
        # Get icon based on status and operation type
        if req.status == ApprovalStatus.APPROVED:
            icon = "approved"
        elif req.status == ApprovalStatus.REJECTED:
            icon = "rejected"
        elif req.operation_type == OperationType.DELETE:
            icon = "delete"
        elif req.operation_type == OperationType.DISABLE:
            icon = "disable"
        elif req.operation_type == OperationType.UNPUBLISH:
            icon = "unpublish"
        else:
            icon = "pending"
        
        result.append({
            "id": req.id,
            "operation_type": req.operation_type.value if hasattr(req.operation_type, 'value') else req.operation_type,
            "target_entity_type": req.target_entity_type,
            "target_entity_id": req.target_entity_id,
            "reason": req.reason,
            "status": req.status.value,
            "approver": approver_name,
            "approved_at": req.approved_at.isoformat() if req.approved_at else None,
            "rejection_reason": req.rejection_reason,
            "created_at": req.created_at.isoformat(),
            "icon": icon
        })
    
    return {"requests": result}

# Get approval statistics for dashboard
@router.get("/stats")
async def get_approval_stats(
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    # Check if user can view stats (Admin, Manager)
    # Role check is handled by get_current_admin_or_presenter dependency
    
    pending_count = db.query(ApprovalRequest).filter(
        ApprovalRequest.status == ApprovalStatus.PENDING
    ).count()
    
    approved_count = db.query(ApprovalRequest).filter(
        ApprovalRequest.status == ApprovalStatus.APPROVED
    ).count()
    
    rejected_count = db.query(ApprovalRequest).filter(
        ApprovalRequest.status == ApprovalStatus.REJECTED
    ).count()
    
    return {
        "pending": pending_count,
        "approved": approved_count,
        "rejected": rejected_count,
        "total": pending_count + approved_count + rejected_count
    }

# Debug endpoint to check all approval requests
@router.get("/debug/all")
async def debug_all_approvals(
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    # Check if user can view stats (Admin, Manager)
    # Role check is handled by get_current_admin_or_presenter dependency
    
    all_requests = db.query(ApprovalRequest).all()
    
    debug_info = {
        "total_requests": len(all_requests),
        "pending_count": len([r for r in all_requests if r.status == ApprovalStatus.PENDING]),
        "approved_count": len([r for r in all_requests if r.status == ApprovalStatus.APPROVED]),
        "rejected_count": len([r for r in all_requests if r.status == ApprovalStatus.REJECTED]),
        "requests": []
    }
    
    for req in all_requests:
        debug_info["requests"].append({
            "id": req.id,
            "requester_id": req.requester_id,
            "operation_type": req.operation_type.value if hasattr(req.operation_type, 'value') else req.operation_type,
            "target_entity_type": req.target_entity_type,
            "target_entity_id": req.target_entity_id,
            "status": req.status.value,
            "reason": req.reason,
            "created_at": req.created_at.isoformat()
        })
    
    return debug_info

# Simple test endpoint
@router.get("/test")
async def test_approvals():
    return {"message": "Approval system is working", "status": "ok"}

# Delete approval request (only for pending requests by the requester)
@router.delete("/{request_id}")
async def delete_approval_request(
    request_id: int,
    token_data: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    # Get current user from token (works for all user types)
    username = token_data.get("sub")
    role = token_data.get("role")
    
    current_user = None
    if role == "Student":
        current_user = db.query(User).filter(User.username == username).first()
    elif role == "Admin":
        current_user = db.query(Admin).filter(Admin.username == username).first()
    elif role == "Presenter":
        current_user = db.query(Presenter).filter(Presenter.username == username).first()
    elif role == "Mentor":
        current_user = db.query(Mentor).filter(Mentor.username == username).first()
    elif role == "Manager":
        current_user = db.query(Manager).filter(Manager.username == username).first()
    
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Get approval request
    approval_request = db.query(ApprovalRequest).filter(
        ApprovalRequest.id == request_id
    ).first()
    
    if not approval_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval request not found"
        )
    
    # Check if user is the requester
    if approval_request.requester_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own approval requests"
        )
    
    # Allow deletion of any approval request (not just pending)
    # Users should be able to delete their own requests regardless of status
    # if approval_request.status != ApprovalStatus.PENDING:
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Only pending approval requests can be deleted"
    #     )
    
    try:
        # Delete related entity status records first
        entity_statuses = db.query(EntityStatus).filter(
            EntityStatus.approval_request_id == request_id
        ).all()
        
        for entity_status in entity_statuses:
            db.delete(entity_status)
        
        # Flush to ensure entity statuses are deleted first
        db.flush()
        
        # Delete the approval request
        db.delete(approval_request)
        db.commit()
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete approval request: {str(e)}"
        )
    
    return {
        "message": "DELETE - course delete",
        "details": f"Requested by: {current_user.username} ({role})",
        "reason": f"Delete course: {approval_request.reason}",
        "icon": "delete",
        "status": "success"
    }