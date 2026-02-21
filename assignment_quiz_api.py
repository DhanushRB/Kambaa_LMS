from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from typing import Optional, List, Any
import os
import shutil
from pathlib import Path
import json

from database import get_db, Session as SessionModel, User
# Import assignment models from assignment_quiz_models (which uses the correct Base)
try:
    from assignment_quiz_models import (
        Assignment, AssignmentSubmission, AssignmentGrade,
        Quiz, QuizQuestion, QuizAttempt, QuizAnswer, QuizResult,
        SubmissionType, QuestionType, AssignmentStatus, QuizStatus
    )
except ImportError:
    # Fallback to assignment_quiz_tables if models not available
    from assignment_quiz_tables import (
        Assignment, AssignmentSubmission, AssignmentGrade,
    )
from auth import get_current_admin, get_current_presenter, get_current_mentor, get_current_user, get_current_admin_or_presenter
from logging_utils import log_student_action
from email_utils import send_content_added_notification

router = APIRouter(prefix="/assignments-quizzes", tags=["Assignments & Quizzes"])

# Test endpoint
@router.get("/test")
async def test_assignment_api():
    """Test endpoint to verify assignment API is working"""
    return {"message": "Assignment API is working", "status": "ok"}

# Upload directories
UPLOAD_BASE_DIR = Path("uploads")
ASSIGNMENT_UPLOAD_DIR = UPLOAD_BASE_DIR / "assignments"
SUBMISSION_UPLOAD_DIR = UPLOAD_BASE_DIR / "submissions"
try:
    ASSIGNMENT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    SUBMISSION_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"Failed to create upload directories: {e}")

# Pydantic Models
class AssignmentCreate(BaseModel):
    session_id: int
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    instructions: Optional[str] = None
    submission_type: SubmissionType = SubmissionType.FILE
    start_date: Optional[datetime] = None
    due_date: datetime
    total_marks: int = Field(default=100, ge=1, le=1000)
    evaluation_criteria: Optional[str] = None

class AssignmentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    instructions: Optional[str] = None
    submission_type: Optional[SubmissionType] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    total_marks: Optional[int] = Field(None, ge=1, le=1000)
    evaluation_criteria: Optional[str] = None

class QuizCreate(BaseModel):
    session_id: int
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    time_limit_minutes: Optional[int] = Field(None, ge=1, le=300)
    total_marks: int = Field(default=100, ge=1, le=1000)
    auto_submit: bool = True

class QuizQuestionCreate(BaseModel):
    question_text: str = Field(..., min_length=1)
    question_type: QuestionType
    options: Optional[List[str]] = None
    correct_answer: str
    marks: int = Field(default=1, ge=1, le=100)

class QuizUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    time_limit_minutes: Optional[int] = Field(None, ge=1, le=300)
    total_marks: Optional[int] = Field(None, ge=1, le=1000)
    auto_submit: Optional[bool] = None

class SubmissionCreate(BaseModel):
    submission_text: Optional[str] = None

class QuizAnswerSubmit(BaseModel):
    question_id: int
    answer_text: Optional[str] = None
    selected_option: Optional[int] = None

class QuizAttemptSubmit(BaseModel):
    quiz_id: int
    answers: List[QuizAnswerSubmit]

class GradeAssignment(BaseModel):
    submission_id: int
    marks_obtained: float = Field(..., ge=0)
    feedback: Optional[str] = None

# Helper Functions
def get_current_user_by_role(role: str):
    """Get current user based on role"""
    if role == "admin":
        return get_current_admin
    elif role == "presenter":
        return get_current_presenter
    elif role == "mentor":
        return get_current_mentor
    elif role == "student":
        return get_current_user
    else:
        raise HTTPException(status_code=400, detail="Invalid role")

def check_assignment_permissions(user, user_type: str, assignment: Assignment, action: str = "view"):
    """Check if user has permission to perform action on assignment"""
    if user_type == "admin":
        return True
    elif user_type == "presenter":
        return assignment.created_by == user.id and assignment.created_by_type == "presenter"
    elif user_type == "mentor":
        return action in ["view", "grade"]
    elif user_type == "student":
        return action in ["view", "submit"]
    return False

def check_quiz_permissions(user, user_type: str, quiz: Quiz, action: str = "view"):
    """Check if user has permission to perform action on quiz"""
    if user_type == "admin":
        return True
    elif user_type == "presenter":
        return quiz.created_by == user.id and quiz.created_by_type == "presenter"
    elif user_type == "mentor":
        return action in ["view"]
    elif user_type == "student":
        return action in ["view", "attempt"]
    return False

# Assignment Endpoints
@router.delete("/assignments/{assignment_id}")
async def delete_assignment(
    assignment_id: Any,
    db: Session = Depends(get_db)
):
    """Delete an assignment"""
    try:
        # Handle prefixed IDs
        if isinstance(assignment_id, str):
            if "_" in assignment_id:
                try:
                    assignment_id = int(assignment_id.split("_")[1])
                except (IndexError, ValueError):
                    pass
            elif assignment_id.isdigit():
                assignment_id = int(assignment_id)

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
        raise HTTPException(status_code=500, detail=f"Failed to delete assignment: {str(e)}")

@router.delete("/quizzes/{quiz_id}")
async def delete_quiz(
    quiz_id: Any,
    db: Session = Depends(get_db)
):
    """Delete a quiz"""
    try:
        # Handle prefixed IDs
        if isinstance(quiz_id, str):
            if "_" in quiz_id:
                try:
                    quiz_id = int(quiz_id.split("_")[1])
                except (IndexError, ValueError):
                    pass
            elif quiz_id.isdigit():
                quiz_id = int(quiz_id)

        quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        
        # Delete related questions, attempts, answers, and results
        db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz_id).delete()
        
        attempts = db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz_id).all()
        for attempt in attempts:
            db.query(QuizAnswer).filter(QuizAnswer.attempt_id == attempt.id).delete()
            db.query(QuizResult).filter(QuizResult.attempt_id == attempt.id).delete()
        
        db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz_id).delete()
        
        db.delete(quiz)
        db.commit()
        
        return {"message": "Quiz deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete quiz: {str(e)}")

@router.post("/assignments")
async def create_assignment(
    assignment_data: AssignmentCreate,
    db: Session = Depends(get_db)
):
    """Create a new assignment (Admin/Presenter/Mentor) - JSON only"""
    try:
        # Try to authenticate user from different roles
        creator_id = 1
        creator_type = "admin"
        
        # Get token from request headers
        from fastapi import Request
        from jose import jwt
        from auth import SECRET_KEY, ALGORITHM
        
        # This is a simplified approach - in production you'd use proper dependency injection
        # For now, we'll just create the assignment with default values
        
        # Verify session exists and determine type
        from cohort_specific_models import CohortCourseSession
        
        session_type = "global"
        # Check if it's a cohort session first
        cohort_session = db.query(CohortCourseSession).filter(
            CohortCourseSession.id == assignment_data.session_id
        ).first()
        
        if cohort_session:
            session_type = "cohort"
        else:
            # Check regular session
            session = db.query(SessionModel).filter(
                SessionModel.id == assignment_data.session_id
            ).first()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

        # Create assignment
        assignment = Assignment(
            session_id=assignment_data.session_id,
            session_type=session_type,
            title=assignment_data.title,
            description=assignment_data.description,
            instructions=assignment_data.instructions,
            file_path=None,
            submission_type=assignment_data.submission_type,
            start_date=assignment_data.start_date,
            due_date=assignment_data.due_date,
            total_marks=assignment_data.total_marks,
            evaluation_criteria=assignment_data.evaluation_criteria,
            created_by=creator_id,
            created_by_type=creator_type
        )

        db.add(assignment)
        db.commit()
        db.refresh(assignment)

        # Send notification
        try:
            await send_content_added_notification(
                db=db,
                session_id=assignment.session_id,
                content_title=assignment.title,
                content_type="ASSIGNMENT",
                session_type=assignment.session_type,
                description=assignment.description
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to trigger notification: {str(e)}")

        return {
            "message": "Assignment created successfully",
            "assignment_id": assignment.id,
            "assignment": {
                "id": assignment.id,
                "title": assignment.title,
                "description": assignment.description,
                "due_date": assignment.due_date,
                "total_marks": assignment.total_marks,
                "submission_type": assignment.submission_type.value,
                "session_type": assignment.session_type,
                "has_file": False
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create assignment: {str(e)}")

@router.post("/assignments/with-file")
async def create_assignment_with_file(
    session_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(None),
    instructions: str = Form(None),
    submission_type: str = Form("FILE"),
    due_date: str = Form(...),
    total_marks: int = Form(100),
    evaluation_criteria: str = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Create a new assignment with file (Admin/Presenter/Mentor)"""
    try:
        # Verify session exists and determine type
        from cohort_specific_models import CohortCourseSession
        
        session_type = "global"
        cohort_session = db.query(CohortCourseSession).filter(
            CohortCourseSession.id == session_id
        ).first()
        
        if cohort_session:
            session_type = "cohort"
        else:
            session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

        # Handle file upload
        file_path = None
        if file:
            file_extension = os.path.splitext(file.filename)[1]
            if file_extension.lower() not in ['.pdf', '.doc', '.docx', '.zip', '.rar']:
                raise HTTPException(status_code=400, detail="Invalid file type. Only PDF, DOC, DOCX, ZIP, RAR allowed")
            
            filename = f"assignment_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
            file_path = ASSIGNMENT_UPLOAD_DIR / filename
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            file_path = str(file_path)

        # Parse due_date
        try:
            due_date_parsed = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
        except:
            due_date_parsed = datetime.strptime(due_date, "%Y-%m-%d")

        # Create assignment
        assignment = Assignment(
            session_id=session_id,
            session_type=session_type,
            title=title,
            description=description,
            instructions=instructions,
            file_path=file_path,
            submission_type=SubmissionType[submission_type],
            start_date=None,
            due_date=due_date_parsed,
            total_marks=total_marks,
            evaluation_criteria=evaluation_criteria,
            created_by=1,  # Default admin
            created_by_type="admin"
        )

        db.add(assignment)
        db.commit()
        db.refresh(assignment)

        # Send notification
        try:
            await send_content_added_notification(
                db=db,
                session_id=assignment.session_id,
                content_title=assignment.title,
                content_type="ASSIGNMENT",
                session_type=assignment.session_type,
                description=assignment.description
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to trigger notification: {str(e)}")

        return {
            "message": "Assignment created successfully",
            "assignment_id": assignment.id,
            "assignment": {
                "id": assignment.id,
                "title": assignment.title,
                "description": assignment.description,
                "due_date": assignment.due_date,
                "total_marks": assignment.total_marks,
                "submission_type": assignment.submission_type.value,
                "session_type": assignment.session_type,
                "has_file": file_path is not None
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create assignment: {str(e)}")
@router.put("/assignments/{assignment_id}")
async def update_assignment(
    assignment_id: int,
    session_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(None),
    instructions: str = Form(None),
    submission_type: str = Form("FILE"),
    due_date: str = Form(...),
    total_marks: int = Form(100),
    evaluation_criteria: str = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Update an existing assignment"""
    try:
        # Get existing assignment
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        # Handle file upload if provided
        if file:
            file_extension = os.path.splitext(file.filename)[1]
            if file_extension.lower() not in ['.pdf', '.doc', '.docx', '.zip', '.rar']:
                raise HTTPException(status_code=400, detail="Invalid file type. Only PDF, DOC, DOCX, ZIP, RAR allowed")
            
            # Delete old file if exists
            if assignment.file_path and os.path.exists(assignment.file_path):
                try:
                    os.remove(assignment.file_path)
                except:
                    pass  # Ignore if file doesn't exist
            
            filename = f"assignment_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
            file_path = ASSIGNMENT_UPLOAD_DIR / filename
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            assignment.file_path = str(file_path)

        # Parse due_date
        try:
            due_date_parsed = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
        except:
            due_date_parsed = datetime.strptime(due_date, "%Y-%m-%d")

        # Update assignment fields
        assignment.title = title
        assignment.description = description
        assignment.instructions = instructions
        assignment.submission_type = SubmissionType[submission_type]
        assignment.due_date = due_date_parsed
        assignment.total_marks = total_marks
        assignment.evaluation_criteria = evaluation_criteria

        db.commit()
        db.refresh(assignment)

        return {
            "message": "Assignment updated successfully",
            "assignment_id": assignment.id,
            "assignment": {
                "id": assignment.id,
                "title": assignment.title,
                "description": assignment.description,
                "due_date": assignment.due_date,
                "total_marks": assignment.total_marks,
                "submission_type": assignment.submission_type.value,
                "has_file": assignment.file_path is not None
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update assignment: {str(e)}")


@router.get("/assignments/session/{session_id}")
async def get_session_assignments(
    session_id: int,
    db: Session = Depends(get_db)
):
    """Get all assignments for a session - accessible without authentication for admin dashboard"""
    try:
        assignments = db.query(Assignment).filter(
            Assignment.session_id == session_id,
            Assignment.is_active == True
        ).all()

        result = []
        for assignment in assignments:
            submission_count = db.query(AssignmentSubmission).filter(
                AssignmentSubmission.assignment_id == assignment.id
            ).count()

            result.append({
                "id": assignment.id,
                "title": assignment.title,
                "description": assignment.description,
                "instructions": assignment.instructions,
                "submission_type": assignment.submission_type.value,
                "start_date": assignment.start_date,
                "due_date": assignment.due_date,
                "total_marks": assignment.total_marks,
                "evaluation_criteria": assignment.evaluation_criteria,
                "has_file": assignment.file_path is not None,
                "submission_count": submission_count,
                "created_at": assignment.created_at
            })

        return {"assignments": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch assignments: {str(e)}")

@router.post("/assignments/{assignment_id}/submit")
async def submit_assignment(
    assignment_id: int,
    submission_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit assignment (Student only)"""
    try:
        # Get assignment
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        # Check due date
        if datetime.now() > assignment.due_date:
            raise HTTPException(status_code=400, detail="Assignment submission deadline has passed")

        # Check if already submitted
        existing_submission = db.query(AssignmentSubmission).filter(
            AssignmentSubmission.assignment_id == assignment_id,
            AssignmentSubmission.student_id == current_user.id
        ).first()
        
        # Handle file upload
        file_path = existing_submission.file_path if existing_submission else None
        file_name = existing_submission.file_name if existing_submission else None
        file_size = existing_submission.file_size if existing_submission else None
        
        if file:
            # If there was an old file, we might want to delete it, but for now we just overwrite the path
            file_extension = os.path.splitext(file.filename)[1]
            allowed_extensions = ['.pdf', '.doc', '.docx', '.txt', '.zip', '.rar', '.7z',
                                 '.csv', '.xlsx', '.xls', '.ppt', '.pptx',
                                 '.jpg', '.jpeg', '.png', '.gif', '.bmp']
            if file_extension.lower() not in allowed_extensions:
                raise HTTPException(status_code=400, detail=f"Invalid file type '{file_extension}'. Allowed: PDF, DOC, DOCX, TXT, ZIP, RAR, CSV, XLSX, PPTX, JPG, PNG")
            
            filename = f"submission_{assignment_id}_{current_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
            full_file_path = SUBMISSION_UPLOAD_DIR / filename
            
            with open(full_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            file_path = str(full_file_path)
            file_name = file.filename
            file_size = os.path.getsize(file_path)

        # Validate submission based on type
        if assignment.submission_type == SubmissionType.FILE and not file and not (existing_submission and existing_submission.file_path):
            raise HTTPException(status_code=400, detail="File submission required")
        elif assignment.submission_type == SubmissionType.TEXT and not submission_text and not (existing_submission and existing_submission.submission_text):
            raise HTTPException(status_code=400, detail="Text submission required")

        if existing_submission:
            # Update existing submission
            existing_submission.submission_text = submission_text if submission_text else existing_submission.submission_text
            existing_submission.file_path = file_path
            existing_submission.file_name = file_name
            existing_submission.file_size = file_size
            existing_submission.submitted_at = datetime.now()
            existing_submission.status = AssignmentStatus.SUBMITTED
            submission = existing_submission
        else:
            # Create new submission
            submission = AssignmentSubmission(
                assignment_id=assignment_id,
                student_id=current_user.id,
                submission_text=submission_text,
                file_path=file_path,
                file_name=file_name,
                file_size=file_size,
                status=AssignmentStatus.SUBMITTED,
                submitted_at=datetime.now()
            )
            db.add(submission)
        db.commit()
        db.refresh(submission)

        db.commit()
        db.refresh(submission)

        # Log student action
        log_student_action(
            student_id=current_user.id,
            student_username=current_user.username,
            action_type="SUBMIT",
            resource_type="ASSIGNMENT",
            resource_id=assignment.id,
            details=f"Submitted assignment: {assignment.title} (ID: {assignment.id})",
            ip_address=None # IP not readily available in this scope, could be added to Depends
        )

        return {
            "message": "Assignment submitted successfully",
            "submission_id": submission.id,
            "submitted_at": submission.submitted_at
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to submit assignment: {str(e)}")

@router.get("/assignments/{assignment_id}/submissions")
async def get_assignment_submissions(
    assignment_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get all submissions for an assignment (Admin/Presenter/Mentor only)"""
    try:
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        submissions = db.query(AssignmentSubmission).filter(
            AssignmentSubmission.assignment_id == assignment_id
        ).all()

        result = []
        for submission in submissions:
            # Get student info
            student = db.query(User).filter(User.id == submission.student_id).first()
            
            # Get grade if exists
            grade = db.query(AssignmentGrade).filter(
                AssignmentGrade.submission_id == submission.id
            ).first()

            result.append({
                "id": submission.id,
                "student_id": submission.student_id,
                "student_name": student.username if student else "Unknown",
                "student_email": student.email if student else "Unknown",
                "submission_text": submission.submission_text,
                "file_name": submission.file_name,
                "file_path": submission.file_path,
                "file_size": submission.file_size,
                "status": submission.status.value,
                "submitted_at": submission.submitted_at,
                "grade": {
                    "marks_obtained": grade.marks_obtained if grade else None,
                    "total_marks": grade.total_marks if grade else None,
                    "percentage": grade.percentage if grade else None,
                    "feedback": grade.feedback if grade else None,
                    "graded_at": grade.graded_at if grade else None
                } if grade else None
            })

        return {
            "submissions": result,
            "assignment": {
                "id": assignment.id,
                "title": assignment.title,
                "description": assignment.description,
                "instructions": assignment.instructions,
                "total_marks": assignment.total_marks,
                "due_date": assignment.due_date,
                "submission_type": assignment.submission_type.value
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch submissions: {str(e)}")

@router.post("/assignments/grade")
async def grade_assignment(
    grade_data: GradeAssignment,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Grade an assignment submission (Admin/Presenter/Mentor only)"""
    try:
        # Get submission
        submission = db.query(AssignmentSubmission).filter(
            AssignmentSubmission.id == grade_data.submission_id
        ).first()
        
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        # Get assignment
        assignment = db.query(Assignment).filter(
            Assignment.id == submission.assignment_id
        ).first()

        if grade_data.marks_obtained > assignment.total_marks:
            raise HTTPException(
                status_code=400, 
                detail=f"Marks cannot exceed total marks ({assignment.total_marks})"
            )

        # Check if already graded
        existing_grade = db.query(AssignmentGrade).filter(
            AssignmentGrade.submission_id == grade_data.submission_id
        ).first()

        if existing_grade:
            # Update existing grade
            existing_grade.marks_obtained = grade_data.marks_obtained
            existing_grade.percentage = (grade_data.marks_obtained / assignment.total_marks) * 100
            existing_grade.feedback = grade_data.feedback
            existing_grade.graded_by = current_user.id
            existing_grade.graded_at = datetime.now()
        else:
            # Create new grade
            percentage = (grade_data.marks_obtained / assignment.total_marks) * 100
            
            grade = AssignmentGrade(
                assignment_id=submission.assignment_id,
                submission_id=grade_data.submission_id,
                student_id=submission.student_id,
                marks_obtained=grade_data.marks_obtained,
                total_marks=assignment.total_marks,
                percentage=percentage,
                feedback=grade_data.feedback,
                graded_by=current_user.id,
                graded_by_type="admin"
            )
            db.add(grade)

        # Update submission status
        submission.status = AssignmentStatus.EVALUATED

        db.commit()

        return {
            "message": "Assignment graded successfully",
            "marks_obtained": grade_data.marks_obtained,
            "percentage": (grade_data.marks_obtained / assignment.total_marks) * 100
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to grade assignment: {str(e)}")

# Quiz Endpoints
@router.post("/quizzes")
async def create_quiz(
    quiz_data: QuizCreate,
    db: Session = Depends(get_db)
):
    """Create a new quiz (Admin/Presenter only)"""
    try:
        # Verify session exists and determine type (check both cohort and regular sessions)
        from cohort_specific_models import CohortCourseSession
        
        session_type = "global"
        cohort_session = db.query(CohortCourseSession).filter(
            CohortCourseSession.id == quiz_data.session_id
        ).first()
        
        if cohort_session:
            session_type = "cohort"
        else:
            session = db.query(SessionModel).filter(
                SessionModel.id == quiz_data.session_id
            ).first()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

        # Create quiz
        quiz = Quiz(
            session_id=quiz_data.session_id,
            session_type=session_type,
            title=quiz_data.title,
            description=quiz_data.description,
            time_limit_minutes=quiz_data.time_limit_minutes,
            total_marks=quiz_data.total_marks,
            auto_submit=quiz_data.auto_submit,
            created_by=1,  # Default admin ID
            created_by_type="admin"
        )

        db.add(quiz)
        db.commit()
        db.refresh(quiz)

        # Send notification
        try:
            await send_content_added_notification(
                db=db,
                session_id=quiz.session_id,
                content_title=quiz.title,
                content_type="QUIZ",
                session_type=quiz.session_type,
                description=quiz.description
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to trigger notification: {str(e)}")

        return {
            "message": "Quiz created successfully",
            "quiz_id": quiz.id,
            "quiz": {
                "id": quiz.id,
                "title": quiz.title,
                "description": quiz.description,
                "time_limit_minutes": quiz.time_limit_minutes,
                "total_marks": quiz.total_marks,
                "auto_submit": quiz.auto_submit,
                "session_type": quiz.session_type
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create quiz: {str(e)}")

@router.put("/quizzes/{quiz_id}")
async def update_quiz(
    quiz_id: int,
    quiz_data: QuizUpdate,
    db: Session = Depends(get_db)
):
    """Update quiz (Admin/Presenter only)"""
    try:
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")

        if quiz_data.title:
            quiz.title = quiz_data.title
        if quiz_data.description is not None:
            quiz.description = quiz_data.description
        if quiz_data.time_limit_minutes is not None:
            quiz.time_limit_minutes = quiz_data.time_limit_minutes
        if quiz_data.total_marks:
            quiz.total_marks = quiz_data.total_marks
        if quiz_data.auto_submit is not None:
            quiz.auto_submit = quiz_data.auto_submit

        db.commit()
        db.refresh(quiz)

        return {
            "message": "Quiz updated successfully",
            "quiz": {
                "id": quiz.id,
                "title": quiz.title,
                "description": quiz.description,
                "time_limit_minutes": quiz.time_limit_minutes,
                "total_marks": quiz.total_marks
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update quiz: {str(e)}")

@router.post("/quizzes/{quiz_id}/questions")
async def add_quiz_question(
    quiz_id: int,
    question_data: QuizQuestionCreate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Add question to quiz (Admin/Presenter only)"""
    try:
        # Verify quiz exists
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")

        # Validate question data
        if question_data.question_type == QuestionType.MCQ and not question_data.options:
            raise HTTPException(status_code=400, detail="MCQ questions must have options")

        # Get next order index
        max_order = db.query(QuizQuestion).filter(
            QuizQuestion.quiz_id == quiz_id
        ).count()

        # Create question
        question = QuizQuestion(
            quiz_id=quiz_id,
            question_text=question_data.question_text,
            question_type=question_data.question_type,
            options=question_data.options,
            correct_answer=question_data.correct_answer,
            marks=question_data.marks,
            order_index=max_order + 1
        )

        db.add(question)
        db.commit()
        db.refresh(question)

        return {
            "message": "Question added successfully",
            "question_id": question.id,
            "question": {
                "id": question.id,
                "question_text": question.question_text,
                "question_type": question.question_type.value,
                "options": question.options,
                "marks": question.marks,
                "order_index": question.order_index
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add question: {str(e)}")

@router.get("/quizzes/{quiz_id}")
async def get_quiz(
    quiz_id: int,
    db: Session = Depends(get_db)
):
    """Get a single quiz by ID"""
    try:
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")

        question_count = db.query(QuizQuestion).filter(
            QuizQuestion.quiz_id == quiz.id
        ).count()

        return {
            "id": quiz.id,
            "title": quiz.title,
            "description": quiz.description,
            "time_limit_minutes": quiz.time_limit_minutes,
            "total_marks": quiz.total_marks,
            "auto_submit": quiz.auto_submit,
            "question_count": question_count,
            "created_at": quiz.created_at
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch quiz: {str(e)}")

@router.get("/quizzes/session/{session_id}")
async def get_session_quizzes(
    session_id: int,
    db: Session = Depends(get_db)
):
    """Get all quizzes for a session - accessible without authentication for admin dashboard"""
    try:
        quizzes = db.query(Quiz).filter(
            Quiz.session_id == session_id,
            Quiz.is_active == True
        ).all()

        result = []
        for quiz in quizzes:
            question_count = db.query(QuizQuestion).filter(
                QuizQuestion.quiz_id == quiz.id
            ).count()

            attempt_count = db.query(QuizAttempt).filter(
                QuizAttempt.quiz_id == quiz.id
            ).count()

            result.append({
                "id": quiz.id,
                "title": quiz.title,
                "description": quiz.description,
                "time_limit_minutes": quiz.time_limit_minutes,
                "total_marks": quiz.total_marks,
                "auto_submit": quiz.auto_submit,
                "question_count": question_count,
                "attempt_count": attempt_count,
                "created_at": quiz.created_at
            })

        return {"quizzes": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch quizzes: {str(e)}")

@router.get("/quizzes/{quiz_id}/questions-admin")
async def get_quiz_questions_admin(
    quiz_id: int,
    db: Session = Depends(get_db)
):
    """Get quiz questions for admin (shows correct answers)"""
    try:
        questions = db.query(QuizQuestion).filter(
            QuizQuestion.quiz_id == quiz_id
        ).order_by(QuizQuestion.order_index).all()

        result = []
        for question in questions:
            result.append({
                "id": question.id,
                "question_text": question.question_text,
                "question_type": question.question_type.value,
                "options": question.options,
                "correct_answer": question.correct_answer,
                "marks": question.marks,
                "order_index": question.order_index
            })

        return {"questions": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get quiz questions: {str(e)}")

@router.delete("/questions/{question_id}")
async def delete_quiz_question(
    question_id: int,
    db: Session = Depends(get_db)
):
    """Delete a quiz question"""
    try:
        question = db.query(QuizQuestion).filter(QuizQuestion.id == question_id).first()
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
        
        db.delete(question)
        db.commit()
        
        return {"message": "Question deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete question: {str(e)}")

@router.get("/quizzes/{quiz_id}/questions")
async def get_quiz_questions(
    quiz_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get quiz questions for attempt (Student only)"""
    try:
        # Verify quiz exists
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")

        # Check if student already has an active attempt
        active_attempt = db.query(QuizAttempt).filter(
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.student_id == current_user.id,
            QuizAttempt.status == QuizStatus.IN_PROGRESS
        ).first()

        if not active_attempt:
            # Create new attempt
            active_attempt = QuizAttempt(
                quiz_id=quiz_id,
                student_id=current_user.id,
                status=QuizStatus.IN_PROGRESS
            )
            db.add(active_attempt)
            db.commit()
            db.refresh(active_attempt)

        # Get questions
        questions = db.query(QuizQuestion).filter(
            QuizQuestion.quiz_id == quiz_id
        ).order_by(QuizQuestion.order_index).all()

        result = []
        for question in questions:
            result.append({
                "id": question.id,
                "question_text": question.question_text,
                "question_type": question.question_type.value,
                "options": question.options if question.question_type == QuestionType.MCQ else None,
                "marks": question.marks
            })

        return {
            "quiz": {
                "id": quiz.id,
                "title": quiz.title,
                "description": quiz.description,
                "time_limit_minutes": quiz.time_limit_minutes,
                "total_marks": quiz.total_marks,
                "auto_submit": quiz.auto_submit
            },
            "attempt_id": active_attempt.id,
            "questions": result,
            "started_at": active_attempt.started_at
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to get quiz questions: {str(e)}")

@router.post("/quizzes/submit")
async def submit_quiz_attempt(
    attempt_data: QuizAttemptSubmit,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit quiz attempt (Student only)"""
    try:
        # Get active attempt
        attempt = db.query(QuizAttempt).filter(
            QuizAttempt.quiz_id == attempt_data.quiz_id,
            QuizAttempt.student_id == current_user.id,
            QuizAttempt.status == QuizStatus.IN_PROGRESS
        ).first()

        if not attempt:
            raise HTTPException(status_code=404, detail="No active quiz attempt found")

        # Get quiz and questions
        quiz = db.query(Quiz).filter(Quiz.id == attempt_data.quiz_id).first()
        questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz.id).all()
        question_dict = {q.id: q for q in questions}

        total_marks_obtained = 0

        # Process answers
        for answer_data in attempt_data.answers:
            question = question_dict.get(answer_data.question_id)
            if not question:
                continue

            is_correct = False
            marks_obtained = 0

            # Auto-evaluate objective questions
            if question.question_type == QuestionType.MCQ:
                if answer_data.selected_option is not None:
                    correct_option = int(question.correct_answer)
                    is_correct = answer_data.selected_option == correct_option
                    marks_obtained = question.marks if is_correct else 0
            elif question.question_type == QuestionType.TRUE_FALSE:
                if answer_data.answer_text:
                    is_correct = answer_data.answer_text.lower().strip() == question.correct_answer.lower().strip()
                    marks_obtained = question.marks if is_correct else 0

            # Create answer record
            quiz_answer = QuizAnswer(
                attempt_id=attempt.id,
                question_id=question.id,
                answer_text=answer_data.answer_text,
                selected_option=answer_data.selected_option,
                is_correct=is_correct,
                marks_obtained=marks_obtained
            )
            db.add(quiz_answer)
            total_marks_obtained += marks_obtained

        # Update attempt
        attempt.status = QuizStatus.COMPLETED
        attempt.submitted_at = datetime.now()
        time_taken = (attempt.submitted_at - attempt.started_at).total_seconds() / 60
        attempt.time_taken_minutes = int(time_taken)

        # Create result
        percentage = (total_marks_obtained / quiz.total_marks) * 100
        grade = "A+" if percentage >= 90 else "A" if percentage >= 80 else "B+" if percentage >= 70 else "B" if percentage >= 60 else "C" if percentage >= 50 else "F"

        result = QuizResult(
            quiz_id=quiz.id,
            attempt_id=attempt.id,
            student_id=current_user.id,
            total_marks=quiz.total_marks,
            marks_obtained=total_marks_obtained,
            percentage=percentage,
            grade=grade,
            auto_evaluated=True
        )
        db.add(result)

        db.commit()

        return {
            "message": "Quiz submitted successfully",
            "result": {
                "total_marks": quiz.total_marks,
                "marks_obtained": total_marks_obtained,
                "percentage": percentage,
                "grade": grade,
                "time_taken_minutes": attempt.time_taken_minutes
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to submit quiz: {str(e)}")

@router.get("/quizzes/{quiz_id}/results")
async def get_quiz_results(
    quiz_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get quiz results (Admin/Presenter/Mentor only)"""
    try:
        results = db.query(QuizResult).filter(QuizResult.quiz_id == quiz_id).all()

        result_list = []
        for result in results:
            # Get student info
            student = db.query(User).filter(User.id == result.student_id).first()
            # Get attempt info
            attempt = db.query(QuizAttempt).filter(QuizAttempt.id == result.attempt_id).first()
            
            result_list.append({
                "id": result.id,
                "student_id": result.student_id,
                "student_name": student.username if student else "Unknown",
                "total_marks": result.total_marks,
                "marks_obtained": result.marks_obtained,
                "percentage": result.percentage,
                "grade": result.grade,
                "time_taken_minutes": attempt.time_taken_minutes if attempt else 0,
                "submitted_at": attempt.submitted_at if attempt else None,
                "auto_evaluated": result.auto_evaluated
            })

        return {"results": result_list}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch quiz results: {str(e)}")

# Student Dashboard Endpoints
@router.get("/student/assignments")
async def get_student_assignments(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get assignments for current student - only from enrolled courses"""
    try:
        from database import CohortCourse, Course, Module, Enrollment
        from cohort_specific_models import CohortSpecificCourse, CohortCourseModule, CohortCourseSession
        
        result = []
        
        # Get student's enrollment status to get all cohort access
        from student_dashboard_endpoints import get_student_enrollment_status
        enrollment_status = get_student_enrollment_status(db, current_user.id)
        
        # Get all relevant cohort IDs
        user_cohorts = enrollment_status.get("user_cohorts", [])
        cohort_ids = [uc.cohort_id for uc in user_cohorts]
        student = db.query(User).filter(User.id == current_user.id).first()
        if student and student.cohort_id and student.cohort_id not in cohort_ids:
            cohort_ids.append(student.cohort_id)
            
        if not cohort_ids:
            return {"assignments": []}
        
        # 1. Get assignments from global courses assigned to student's cohorts
        active_course_ids = list(enrollment_status.get("enrolled_regular_course_ids", set()))
        
        if active_course_ids:
            modules = db.query(Module).filter(Module.course_id.in_(active_course_ids)).all()
            
            if modules:
                module_ids = [m.id for m in modules]
                sessions = db.query(SessionModel).filter(SessionModel.module_id.in_(module_ids)).all()
                
                if sessions:
                    session_ids = [s.id for s in sessions]
                    assignments = db.query(Assignment).filter(
                        Assignment.session_id.in_(session_ids),
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
                        
                        session = db.query(SessionModel).filter(SessionModel.id == assignment.session_id).first()
                        module = db.query(Module).filter(Module.id == session.module_id).first() if session else None
                        course = db.query(Course).filter(Course.id == module.course_id).first() if module else None

                        result.append({
                            "id": assignment.id,
                            "title": assignment.title,
                            "description": assignment.description,
                            "instructions": assignment.instructions,
                            "file_path": assignment.file_path,  # Add file_path for assignment materials
                            "due_date": assignment.due_date,
                            "total_marks": assignment.total_marks,
                            "submission_type": assignment.submission_type.value,
                            "status": submission.status.value if submission else "PENDING",
                            "submitted_at": submission.submitted_at if submission else None,
                            "grade": grade,
                            "session_title": session.title if session else "Unknown",
                            "module_title": module.title if module else "Unknown",
                            "course_title": course.title if course else "Unknown",
                            "course_type": "regular"
                        })
        
        # 2. Get assignments from cohort-specific courses assigned to student's cohorts
        cohort_course_ids = list(enrollment_status.get("enrolled_cohort_course_ids", set()))
        
        if cohort_course_ids:
            
            if cohort_course_ids:
                cohort_modules = db.query(CohortCourseModule).filter(
                    CohortCourseModule.course_id.in_(cohort_course_ids)
                ).all()
            
                if cohort_modules:
                    cohort_module_ids = [m.id for m in cohort_modules]
                    cohort_sessions = db.query(CohortCourseSession).filter(
                        CohortCourseSession.module_id.in_(cohort_module_ids)
                    ).all()
                    
                    if cohort_sessions:
                        cohort_session_ids = [s.id for s in cohort_sessions]
                        cohort_assignments = db.query(Assignment).filter(
                            Assignment.session_id.in_(cohort_session_ids),
                            Assignment.session_type == "cohort",
                            Assignment.is_active == True
                        ).all()

                        for assignment in cohort_assignments:
                            submission = db.query(AssignmentSubmission).filter(
                                AssignmentSubmission.assignment_id == assignment.id,
                                AssignmentSubmission.student_id == current_user.id
                            ).first()

                            grade = None
                            if submission:
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
                            
                            cohort_session = db.query(CohortCourseSession).filter(
                                CohortCourseSession.id == assignment.session_id
                            ).first()
                            cohort_module = db.query(CohortCourseModule).filter(
                                CohortCourseModule.id == cohort_session.module_id
                            ).first() if cohort_session else None
                            cohort_course = db.query(CohortSpecificCourse).filter(
                                CohortSpecificCourse.id == cohort_module.course_id
                            ).first() if cohort_module else None

                            result.append({
                                "id": assignment.id,
                                "title": assignment.title,
                                "description": assignment.description,
                                "instructions": assignment.instructions,
                                "file_path": assignment.file_path,  # Add file_path for assignment materials
                                "due_date": assignment.due_date,
                                "total_marks": assignment.total_marks,
                                "submission_type": assignment.submission_type.value,
                                "status": submission.status.value if submission else "PENDING",
                                "submitted_at": submission.submitted_at if submission else None,
                                "grade": grade,
                                "session_title": cohort_session.title if cohort_session else "Unknown",
                                "module_title": cohort_module.title if cohort_module else "Unknown",
                                "course_title": cohort_course.title if cohort_course else "Unknown",
                                "course_type": "cohort_specific"
                            })

        return {"assignments": result}

    except Exception as e:
        import traceback
        print(f"Error fetching student assignments: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch student assignments: {str(e)}")

@router.get("/student/quizzes")
async def get_student_quizzes(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get quizzes for current student - only from enrolled courses"""
    try:
        from database import CohortCourse, Course, Module, Enrollment
        from cohort_specific_models import CohortSpecificCourse, CohortCourseModule, CohortCourseSession
        
        result = []
        
        # Get student's enrollment status to get all cohort access
        from student_dashboard_endpoints import get_student_enrollment_status
        enrollment_status = get_student_enrollment_status(db, current_user.id)
        
        # Get all relevant cohort IDs
        user_cohorts = enrollment_status.get("user_cohorts", [])
        cohort_ids = [uc.cohort_id for uc in user_cohorts]
        student = db.query(User).filter(User.id == current_user.id).first()
        if student and student.cohort_id and student.cohort_id not in cohort_ids:
            cohort_ids.append(student.cohort_id)
            
        if not cohort_ids:
            return {"quizzes": []}
        
        # 1. Get quizzes from global courses assigned to student's cohorts
        active_course_ids = list(enrollment_status.get("enrolled_regular_course_ids", set()))
        
        if active_course_ids:
            modules = db.query(Module).filter(Module.course_id.in_(active_course_ids)).all()
            
            if modules:
                module_ids = [m.id for m in modules]
                sessions = db.query(SessionModel).filter(SessionModel.module_id.in_(module_ids)).all()
                
                if sessions:
                    session_ids = [s.id for s in sessions]
                    quizzes = db.query(Quiz).filter(
                        Quiz.session_id.in_(session_ids),
                        Quiz.is_active == True
                    ).all()

                for quiz in quizzes:
                    # Check attempt status
                    attempt = db.query(QuizAttempt).filter(
                        QuizAttempt.quiz_id == quiz.id,
                        QuizAttempt.student_id == current_user.id
                    ).first()

                    # Get result if exists
                    quiz_result = None
                    if attempt and attempt.status == QuizStatus.COMPLETED:
                        result_record = db.query(QuizResult).filter(
                            QuizResult.attempt_id == attempt.id
                        ).first()
                        if result_record:
                            quiz_result = {
                                "marks_obtained": result_record.marks_obtained,
                                "total_marks": result_record.total_marks,
                                "percentage": result_record.percentage,
                                "grade": result_record.grade,
                                "time_taken_minutes": attempt.time_taken_minutes
                            }
                    
                    # Get session and module info
                    session = db.query(SessionModel).filter(SessionModel.id == quiz.session_id).first()
                    module = db.query(Module).filter(Module.id == session.module_id).first() if session else None
                    course = db.query(Course).filter(Course.id == module.course_id).first() if module else None

                    result.append({
                        "id": quiz.id,
                        "title": quiz.title,
                        "description": quiz.description,
                        "time_limit_minutes": quiz.time_limit_minutes,
                        "total_marks": quiz.total_marks,
                        "status": attempt.status.value if attempt else "NOT_ATTEMPTED",
                        "result": quiz_result,
                        "session_title": session.title if session else "Unknown",
                        "module_title": module.title if module else "Unknown",
                        "course_title": course.title if course else "Unknown"
                    })
        
        # 2. Get quizzes from cohort-specific courses assigned to student's cohorts
        cohort_course_ids = list(enrollment_status.get("enrolled_cohort_course_ids", set()))
        
        if cohort_course_ids:
            
            if cohort_course_ids:
                cohort_modules = db.query(CohortCourseModule).filter(
                    CohortCourseModule.course_id.in_(cohort_course_ids)
                ).all()
            
            if cohort_modules:
                cohort_module_ids = [m.id for m in cohort_modules]
                cohort_sessions = db.query(CohortCourseSession).filter(
                    CohortCourseSession.module_id.in_(cohort_module_ids)
                ).all()
                
                if cohort_sessions:
                    cohort_session_ids = [s.id for s in cohort_sessions]
                    cohort_quizzes = db.query(Quiz).filter(
                        Quiz.session_id.in_(cohort_session_ids),
                        Quiz.is_active == True
                    ).all()

                    for quiz in cohort_quizzes:
                        # Check attempt status
                        attempt = db.query(QuizAttempt).filter(
                            QuizAttempt.quiz_id == quiz.id,
                            QuizAttempt.student_id == current_user.id
                        ).first()

                        # Get result if exists
                        quiz_result = None
                        if attempt and attempt.status == QuizStatus.COMPLETED:
                            result_record = db.query(QuizResult).filter(
                                QuizResult.attempt_id == attempt.id
                            ).first()
                            if result_record:
                                quiz_result = {
                                    "marks_obtained": result_record.marks_obtained,
                                    "total_marks": result_record.total_marks,
                                    "percentage": result_record.percentage,
                                    "grade": result_record.grade,
                                    "time_taken_minutes": attempt.time_taken_minutes
                                }
                        
                        cohort_session = db.query(CohortCourseSession).filter(
                            CohortCourseSession.id == quiz.session_id
                        ).first()
                        cohort_module = db.query(CohortCourseModule).filter(
                            CohortCourseModule.id == cohort_session.module_id
                        ).first() if cohort_session else None
                        cohort_course = db.query(CohortSpecificCourse).filter(
                            CohortSpecificCourse.id == cohort_module.course_id
                        ).first() if cohort_module else None

                        result.append({
                            "id": quiz.id,
                            "title": quiz.title,
                            "description": quiz.description,
                            "time_limit_minutes": quiz.time_limit_minutes,
                            "total_marks": quiz.total_marks,
                            "status": attempt.status.value if attempt else "NOT_ATTEMPTED",
                            "result": quiz_result,
                            "session_title": cohort_session.title if cohort_session else "Unknown",
                            "module_title": cohort_module.title if cohort_module else "Unknown",
                            "course_title": cohort_course.title if cohort_course else "Unknown"
                        })

        return {"quizzes": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch student quizzes: {str(e)}")

# Admin Analytics Endpoints
@router.get("/admin/assignment-analytics")
async def get_assignment_analytics(
    db: Session = Depends(get_db)
):
    """Get assignment analytics for admin dashboard"""
    try:
        from database import Course, Module
        
        assignments = db.query(Assignment).filter(Assignment.is_active == True).all()
        
        result = []
        for assignment in assignments:
            # Get submission stats
            total_submissions = db.query(AssignmentSubmission).filter(
                AssignmentSubmission.assignment_id == assignment.id
            ).count()
            
            pending_review = db.query(AssignmentSubmission).filter(
                AssignmentSubmission.assignment_id == assignment.id,
                AssignmentSubmission.status == AssignmentStatus.SUBMITTED
            ).count()
            
            graded = db.query(AssignmentGrade).filter(
                AssignmentGrade.assignment_id == assignment.id
            ).count()
            
            # Calculate average score
            grades = db.query(AssignmentGrade).filter(
                AssignmentGrade.assignment_id == assignment.id
            ).all()
            
            average_score = None
            if grades:
                total_percentage = sum(g.percentage for g in grades)
                average_score = total_percentage / len(grades)
            
            # Get course info
            session = db.query(SessionModel).filter(SessionModel.id == assignment.session_id).first()
            module = db.query(Module).filter(Module.id == session.module_id).first() if session else None
            course = db.query(Course).filter(Course.id == module.course_id).first() if module else None
            
            result.append({
                "id": assignment.id,
                "title": assignment.title,
                "course_title": course.title if course else "Unknown",
                "due_date": assignment.due_date,
                "total_submissions": total_submissions,
                "pending_review": pending_review,
                "graded": graded,
                "average_score": average_score
            })
        
        return {"assignments": result}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch assignment analytics: {str(e)}")