from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

from database import get_db, User, Enrollment, Course, Session as SessionModel
from auth import get_current_user, get_current_user_any_role
from cohort_specific_models import CohortSpecificEnrollment, CohortSpecificCourse, CohortCourseSession
from feedback_models import (
    FeedbackForm, FeedbackQuestion, FeedbackSubmission, FeedbackAnswer,
    QuestionType
)
from email_utils import send_feedback_submission_confirmation, send_feedback_request_to_students

router = APIRouter(prefix="/feedback", tags=["feedback"])
logger = logging.getLogger(__name__)

# Pydantic schemas
class QuestionCreate(BaseModel):
    question_text: str
    question_type: str  # TEXT, LONG_TEXT, RATING, MULTIPLE_CHOICE, CHECKBOX
    options: Optional[List[str]] = None
    is_required: bool = True
    order_index: int = 0

class FeedbackFormCreate(BaseModel):
    session_id: int
    session_type: str  # global or cohort
    title: str
    description: Optional[str] = None
    is_anonymous: bool = False
    allow_multiple_submissions: bool = False
    questions: List[QuestionCreate]

class FeedbackFormUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_anonymous: Optional[bool] = None
    allow_multiple_submissions: Optional[bool] = None
    is_active: Optional[bool] = None
    questions: Optional[List[QuestionCreate]] = None

class AnswerSubmit(BaseModel):
    question_id: int
    answer_text: Optional[str] = None
    answer_value: Optional[int] = None
    answer_choices: Optional[List[str]] = None

class FeedbackSubmit(BaseModel):
    answers: List[AnswerSubmit]

# Helper function to check staff roles
def is_staff(user_info) -> bool:
    role = user_info.get("role") if isinstance(user_info, dict) else getattr(user_info, "role", None)
    return role in ["Admin", "Presenter", "Manager", "Mentor"]

# ==================== FORM MANAGEMENT (STAFF ONLY) ====================

@router.post("/forms", status_code=status.HTTP_201_CREATED)
async def create_feedback_form(
    form_data: FeedbackFormCreate,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Create a new feedback form (Staff only)"""
    try:
        if not is_staff(current_user):
            raise HTTPException(status_code=403, detail="Only staff can create feedback forms")
        
        user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
        
        # Create form
        new_form = FeedbackForm(
            session_id=form_data.session_id,
            session_type=form_data.session_type,
            title=form_data.title,
            description=form_data.description,
            is_anonymous=form_data.is_anonymous,
            allow_multiple_submissions=form_data.allow_multiple_submissions,
            created_by=user_id
        )
        db.add(new_form)
        db.flush()
        
        # Create questions
        for q_data in form_data.questions:
            question = FeedbackQuestion(
                form_id=new_form.id,
                question_text=q_data.question_text,
                question_type=QuestionType[q_data.question_type],
                options=q_data.options,
                is_required=q_data.is_required,
                order_index=q_data.order_index
            )
            db.add(question)
        
        db.commit()
        db.refresh(new_form)
        
        logger.info(f"Feedback form created: {new_form.id} by user {user_id}")
        
        # Trigger feedback request notification to all eligible students
        background_tasks.add_task(
            send_feedback_request_to_students,
            db=db,
            feedback_title=new_form.title,
            session_id=new_form.session_id,
            session_type=new_form.session_type
        )
        
        return {"message": "Feedback form created successfully", "form_id": new_form.id}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create feedback form error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create feedback form: {str(e)}")

@router.get("/forms/{form_id}")
async def get_feedback_form(
    form_id: int,
    current_user = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Get feedback form details with questions"""
    try:
        form = db.query(FeedbackForm).filter(FeedbackForm.id == form_id).first()
        if not form:
            raise HTTPException(status_code=404, detail="Feedback form not found")
        
        questions = db.query(FeedbackQuestion).filter(
            FeedbackQuestion.form_id == form_id
        ).order_by(FeedbackQuestion.order_index).all()
        
        return {
            "id": form.id,
            "session_id": form.session_id,
            "session_type": form.session_type,
            "title": form.title,
            "description": form.description,
            "is_anonymous": form.is_anonymous,
            "allow_multiple_submissions": form.allow_multiple_submissions,
            "is_active": form.is_active,
            "created_at": form.created_at,
            "questions": [
                {
                    "id": q.id,
                    "question_text": q.question_text,
                    "question_type": q.question_type.value,
                    "options": q.options,
                    "is_required": q.is_required,
                    "order_index": q.order_index
                }
                for q in questions
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get feedback form error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch feedback form")

@router.put("/forms/{form_id}")
async def update_feedback_form(
    form_id: int,
    form_data: FeedbackFormUpdate,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Update feedback form (Staff only)"""
    try:
        if not is_staff(current_user):
            raise HTTPException(status_code=403, detail="Only staff can update feedback forms")
        
        form = db.query(FeedbackForm).filter(FeedbackForm.id == form_id).first()
        if not form:
            raise HTTPException(status_code=404, detail="Feedback form not found")
        
        # Update form metadata
        if form_data.title is not None:
            form.title = form_data.title
        if form_data.description is not None:
            form.description = form_data.description
        if form_data.is_anonymous is not None:
            form.is_anonymous = form_data.is_anonymous
        if form_data.allow_multiple_submissions is not None:
            form.allow_multiple_submissions = form_data.allow_multiple_submissions
        if form_data.is_active is not None:
            form.is_active = form_data.is_active
        
        # Update questions if provided
        if form_data.questions is not None:
            # Delete existing questions
            db.query(FeedbackQuestion).filter(FeedbackQuestion.form_id == form_id).delete()
            
            # Create new questions
            for q_data in form_data.questions:
                question = FeedbackQuestion(
                    form_id=form_id,
                    question_text=q_data.question_text,
                    question_type=QuestionType[q_data.question_type],
                    options=q_data.options,
                    is_required=q_data.is_required,
                    order_index=q_data.order_index
                )
                db.add(question)
        
        form.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Feedback form {form_id} updated by user {current_user.get('id') if isinstance(current_user, dict) else current_user.id}")
        
        # Trigger feedback request notification to all eligible students
        background_tasks.add_task(
            send_feedback_request_to_students,
            db=db,
            feedback_title=form.title,
            session_id=form.session_id,
            session_type=form.session_type
        )
        
        return {"message": "Feedback form updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update feedback form error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update feedback form")

@router.delete("/forms/{form_id}")
async def delete_feedback_form(
    form_id: int,
    current_user = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Delete feedback form (Staff only)"""
    try:
        if not is_staff(current_user):
            raise HTTPException(status_code=403, detail="Only staff can delete feedback forms")
        
        form = db.query(FeedbackForm).filter(FeedbackForm.id == form_id).first()
        if not form:
            raise HTTPException(status_code=404, detail="Feedback form not found")
        
        db.delete(form)
        db.commit()
        
        return {"message": "Feedback form deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete feedback form error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete feedback form")

@router.post("/forms/{form_id}/clone", status_code=status.HTTP_201_CREATED)
async def clone_feedback_form(
    form_id: int,
    target_session_id: int,
    session_type: str = "global",
    current_user = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Clone a feedback form to another session (Staff only)"""
    try:
        if not is_staff(current_user):
            raise HTTPException(status_code=403, detail="Only staff can clone feedback forms")
        
        user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
        
        # Get source form with questions
        source_form = db.query(FeedbackForm).filter(FeedbackForm.id == form_id).first()
        if not source_form:
            raise HTTPException(status_code=404, detail="Source feedback form not found")
        
        source_questions = db.query(FeedbackQuestion).filter(
            FeedbackQuestion.form_id == form_id
        ).order_by(FeedbackQuestion.order_index).all()
        
        # Create new form
        new_form = FeedbackForm(
            session_id=target_session_id,
            session_type=session_type,
            title=f"{source_form.title} (Cloned)",
            description=source_form.description,
            is_anonymous=source_form.is_anonymous,
            allow_multiple_submissions=source_form.allow_multiple_submissions,
            created_by=user_id
        )
        db.add(new_form)
        db.flush()
        
        # Clone all questions
        for source_q in source_questions:
            new_question = FeedbackQuestion(
                form_id=new_form.id,
                question_text=source_q.question_text,
                question_type=source_q.question_type,
                options=source_q.options,
                is_required=source_q.is_required,
                order_index=source_q.order_index
            )
            db.add(new_question)
        
        db.commit()
        db.refresh(new_form)
        
        logger.info(f"Feedback form cloned: {form_id} -> {new_form.id} by user {user_id}")
        return {
            "message": "Feedback form cloned successfully",
            "form_id": new_form.id,
            "questions_cloned": len(source_questions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Clone feedback form error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clone feedback form: {str(e)}")


@router.get("/sessions/{session_id}/forms")
async def get_session_feedback_forms(
    session_id: int,
    session_type: str = "global",
    current_user = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Get all feedback forms for a session"""
    try:
        forms = db.query(FeedbackForm).filter(
            FeedbackForm.session_id == session_id,
            FeedbackForm.session_type == session_type,
            FeedbackForm.is_active == True
        ).all()
        
        result = []
        for form in forms:
            # Count submissions
            submission_count = db.query(func.count(FeedbackSubmission.id)).filter(
                FeedbackSubmission.form_id == form.id
            ).scalar()
            
            # Count questions
            question_count = db.query(func.count(FeedbackQuestion.id)).filter(
                FeedbackQuestion.form_id == form.id
            ).scalar()
            
            result.append({
                "id": form.id,
                "title": form.title,
                "description": form.description,
                "is_anonymous": form.is_anonymous,
                "question_count": question_count,
                "submission_count": submission_count,
                "created_at": form.created_at
            })
        
        return {"forms": result}
        
    except Exception as e:
        logger.error(f"Get session feedback forms error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch feedback forms")

# ==================== STUDENT ENDPOINTS ====================

@router.get("/student/sessions/{session_id}/forms")
async def get_student_feedback_forms(
    session_id: int,
    session_type: str = "global",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get available feedback forms for student"""
    try:
        forms = db.query(FeedbackForm).filter(
            FeedbackForm.session_id == session_id,
            FeedbackForm.session_type == session_type,
            FeedbackForm.is_active == True
        ).all()
        
        result = []
        for form in forms:
            # Check if student has submitted
            submission = db.query(FeedbackSubmission).filter(
                FeedbackSubmission.form_id == form.id,
                FeedbackSubmission.student_id == current_user.id
            ).first()
            
            result.append({
                "id": form.id,
                "title": form.title,
                "description": form.description,
                "is_anonymous": form.is_anonymous,
                "has_submitted": submission is not None,
                "submitted_at": submission.submitted_at if submission else None
            })
        
        return {"forms": result}
        
    except Exception as e:
        logger.error(f"Get student feedback forms error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch feedback forms")

@router.get("/student/available-forms")
async def get_student_available_feedback_forms(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Aggregate all available feedback forms for student's enrolled/cohort courses"""
    try:
        logger.info(f"Fetching feedback forms for student ID: {current_user.id}")
        
        # 1. Get all cohorts the student is in
        from database import UserCohort, CohortCourse
        user_cohorts = db.query(UserCohort).filter(
            UserCohort.user_id == current_user.id,
            UserCohort.is_active == True
        ).all()
        cohort_ids = [uc.cohort_id for uc in user_cohorts]
        # Also include cohort_id from User table if not in UserCohort
        if current_user.cohort_id and current_user.cohort_id not in cohort_ids:
            cohort_ids.append(current_user.cohort_id)
        
        logger.info(f"Student is in cohorts: {cohort_ids}")
        
        # 2. Collect all regular course IDs (Direct enrollment + Cohort assigned)
        enrollments = db.query(Enrollment).filter(Enrollment.student_id == current_user.id).all()
        course_ids = [e.course_id for e in enrollments]
        
        if cohort_ids:
            # Regular courses assigned to cohorts (Legacy)
            cc_assignments = db.query(CohortCourse).filter(CohortCourse.cohort_id.in_(cohort_ids)).all()
            for cc in cc_assignments:
                if cc.course_id not in course_ids:
                    course_ids.append(cc.course_id)
            
            # Regular courses assigned to cohorts (Unified)
            try:
                from database import CourseAssignment
                unified_assignments = db.query(CourseAssignment).filter(
                    CourseAssignment.cohort_id.in_(cohort_ids),
                    CourseAssignment.assignment_type == 'cohort'
                ).all()
                for ua in unified_assignments:
                    if ua.course_id not in course_ids:
                        course_ids.append(ua.course_id)
            except ImportError:
                pass
                
        logger.info(f"Total regular course IDs for student: {course_ids}")
        
        # 3. Collect all cohort-specific course IDs
        cohort_specific_course_ids = []
        # Direct enrollments
        cs_enrollments = db.query(CohortSpecificEnrollment).filter(
            CohortSpecificEnrollment.student_id == current_user.id
        ).all()
        cohort_specific_course_ids = [e.course_id for e in cs_enrollments]
        
        # All courses in student's cohorts
        if cohort_ids:
            cs_courses = db.query(CohortSpecificCourse).filter(
                CohortSpecificCourse.cohort_id.in_(cohort_ids),
                CohortSpecificCourse.is_active == True
            ).all()
            for c in cs_courses:
                if c.id not in cohort_specific_course_ids:
                    cohort_specific_course_ids.append(c.id)
                    
        logger.info(f"Total cohort-specific course IDs for student: {cohort_specific_course_ids}")
        
        available_forms = []
        
        # 4. Find forms for regular courses
        if course_ids:
            from database import Module
            sessions = db.query(SessionModel).join(Module).filter(
                Module.course_id.in_(course_ids)
            ).all()
            session_ids = [s.id for s in sessions]
            logger.info(f"Found {len(session_ids)} regular sessions")
            
            if session_ids:
                global_forms = db.query(FeedbackForm).filter(
                    FeedbackForm.session_id.in_(session_ids),
                    FeedbackForm.session_type == "global",
                    FeedbackForm.is_active == True
                ).all()
                logger.info(f"Found {len(global_forms)} active global forms")
                
                for form in global_forms:
                    session = next((s for s in sessions if s.id == form.session_id), None)
                    course_title = "Unknown Course"
                    if session and session.module and session.module.course:
                        course_title = session.module.course.title
                    
                    # Check submission
                    submission = db.query(FeedbackSubmission).filter(
                        FeedbackSubmission.form_id == form.id,
                        FeedbackSubmission.student_id == current_user.id
                    ).first()
                    
                    available_forms.append({
                        "id": form.id,
                        "title": form.title,
                        "description": form.description,
                        "course_title": course_title,
                        "session_title": session.title if session else "General",
                        "session_type": "global",
                        "is_anonymous": form.is_anonymous,
                        "has_submitted": submission is not None,
                        "submitted_at": submission.submitted_at if submission else None,
                        "created_at": form.created_at
                    })
        
        # 5. Find forms for cohort-specific courses
        if cohort_specific_course_ids:
            from cohort_specific_models import CohortCourseModule
            cohort_sessions = db.query(CohortCourseSession).join(CohortCourseModule).filter(
                CohortCourseModule.course_id.in_(cohort_specific_course_ids)
            ).all()
            cohort_session_ids = [s.id for s in cohort_sessions]
            logger.info(f"Found {len(cohort_session_ids)} cohort sessions")
            
            if cohort_session_ids:
                cohort_forms = db.query(FeedbackForm).filter(
                    FeedbackForm.session_id.in_(cohort_session_ids),
                    FeedbackForm.session_type == "cohort",
                    FeedbackForm.is_active == True
                ).all()
                logger.info(f"Found {len(cohort_forms)} active cohort forms")
                
                for form in cohort_forms:
                    session = next((s for s in cohort_sessions if s.id == form.session_id), None)
                    course_title = "Unknown Cohort Course"
                    if session and session.module and session.module.course:
                        course_title = session.module.course.title
                        
                    # Check submission
                    submission = db.query(FeedbackSubmission).filter(
                        FeedbackSubmission.form_id == form.id,
                        FeedbackSubmission.student_id == current_user.id
                    ).first()
                    
                    available_forms.append({
                        "id": form.id,
                        "title": form.title,
                        "description": form.description,
                        "course_title": course_title,
                        "session_title": session.title if session else "General",
                        "session_type": "cohort",
                        "is_anonymous": form.is_anonymous,
                        "has_submitted": submission is not None,
                        "submitted_at": submission.submitted_at if submission else None,
                        "created_at": form.created_at
                    })
        
        logger.info(f"Total available forms for student: {len(available_forms)}")
        # Sort by creation date
        available_forms.sort(key=lambda x: x["created_at"], reverse=True)
        
        return {"forms": available_forms}
    except Exception as e:
        logger.error(f"Get student available forms error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/student/forms/{form_id}")
async def get_student_feedback_form(
    form_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get feedback form for student submission"""
    try:
        form = db.query(FeedbackForm).filter(
            FeedbackForm.id == form_id,
            FeedbackForm.is_active == True
        ).first()
        
        if not form:
            raise HTTPException(status_code=404, detail="Feedback form not found")
        
        # Check if already submitted
        submission = db.query(FeedbackSubmission).filter(
            FeedbackSubmission.form_id == form_id,
            FeedbackSubmission.student_id == current_user.id
        ).first()
        
        # Get answers if submitted
        submitted_answers = []
        if submission:
            answers = db.query(FeedbackAnswer).filter(
                FeedbackAnswer.submission_id == submission.id
            ).all()
            submitted_answers = [
                {
                    "question_id": a.question_id,
                    "answer_text": a.answer_text,
                    "answer_value": a.answer_value,
                    "answer_choices": a.answer_choices
                }
                for a in answers
            ]
        
        questions = db.query(FeedbackQuestion).filter(
            FeedbackQuestion.form_id == form_id
        ).order_by(FeedbackQuestion.order_index).all()
        
        return {
            "id": form.id,
            "title": form.title,
            "description": form.description,
            "is_anonymous": form.is_anonymous,
            "has_submitted": submission is not None,
            "submitted_at": submission.submitted_at if submission else None,
            "submitted_answers": submitted_answers,
            "questions": [
                {
                    "id": q.id,
                    "question_text": q.question_text,
                    "question_type": q.question_type.value,
                    "options": q.options,
                    "is_required": q.is_required
                }
                for q in questions
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get student feedback form error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch feedback form")

@router.post("/student/forms/{form_id}/submit")
async def submit_feedback(
    form_id: int,
    submission_data: FeedbackSubmit,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit feedback form"""
    try:
        form = db.query(FeedbackForm).filter(
            FeedbackForm.id == form_id,
            FeedbackForm.is_active == True
        ).first()
        
        if not form:
            raise HTTPException(status_code=404, detail="Feedback form not found")
        
        # Check if already submitted
        existing_submission = db.query(FeedbackSubmission).filter(
            FeedbackSubmission.form_id == form_id,
            FeedbackSubmission.student_id == current_user.id
        ).first()
        
        if existing_submission and not form.allow_multiple_submissions:
            raise HTTPException(status_code=400, detail="You have already submitted this feedback")
        
        # Create submission
        submission = FeedbackSubmission(
            form_id=form_id,
            student_id=None if form.is_anonymous else current_user.id,
            session_id=form.session_id,
            session_type=form.session_type,
            is_anonymous=form.is_anonymous
        )
        db.add(submission)
        db.flush()
        
        # Create answers
        for answer_data in submission_data.answers:
            answer = FeedbackAnswer(
                submission_id=submission.id,
                question_id=answer_data.question_id,
                answer_text=answer_data.answer_text,
                answer_value=answer_data.answer_value,
                answer_choices=answer_data.answer_choices
            )
            db.add(answer)
        
        db.commit()
        
        logger.info(f"Feedback submitted: form={form_id}, user={current_user.id}")
        
        # Trigger email notification as a background task if not anonymous
        if not form.is_anonymous:
            background_tasks.add_task(
                send_feedback_submission_confirmation,
                db=db,
                student_id=current_user.id,
                feedback_title=form.title,
                session_id=form.session_id,
                session_type=form.session_type
            )
            
        return {"message": "Feedback submitted successfully", "submission_id": submission.id}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Submit feedback error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to submit feedback")

# ==================== SUBMISSIONS & ANALYTICS (STAFF ONLY) ====================

@router.get("/forms/{form_id}/submissions")
async def get_form_submissions(
    form_id: int,
    current_user = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Get all submissions for a feedback form (Staff only)"""
    try:
        if not is_staff(current_user):
            raise HTTPException(status_code=403, detail="Only staff can view submissions")
        
        form = db.query(FeedbackForm).filter(FeedbackForm.id == form_id).first()
        if not form:
            raise HTTPException(status_code=404, detail="Feedback form not found")
        
        submissions = db.query(FeedbackSubmission).filter(
            FeedbackSubmission.form_id == form_id
        ).order_by(FeedbackSubmission.submitted_at.desc()).all()
        
        result = []
        for sub in submissions:
            student_name = "Anonymous"
            if not sub.is_anonymous and sub.student_id:
                student = db.query(User).filter(User.id == sub.student_id).first()
                if student:
                    student_name = student.username
            
            result.append({
                "id": sub.id,
                "student_name": student_name,
                "student_id": sub.student_id if not sub.is_anonymous else None,
                "submitted_at": sub.submitted_at,
                "is_anonymous": sub.is_anonymous
            })
        
        return {"submissions": result, "total": len(result)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get form submissions error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch submissions")

@router.get("/submissions/{submission_id}")
async def get_submission_details(
    submission_id: int,
    current_user = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Get detailed submission with answers (Staff only)"""
    try:
        if not is_staff(current_user):
            raise HTTPException(status_code=403, detail="Only staff can view submission details")
        
        submission = db.query(FeedbackSubmission).filter(
            FeedbackSubmission.id == submission_id
        ).first()
        
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        
        answers = db.query(FeedbackAnswer, FeedbackQuestion).join(
            FeedbackQuestion, FeedbackAnswer.question_id == FeedbackQuestion.id
        ).filter(FeedbackAnswer.submission_id == submission_id).all()
        
        student_name = "Anonymous"
        if not submission.is_anonymous and submission.student_id:
            student = db.query(User).filter(User.id == submission.student_id).first()
            if student:
                student_name = student.username
        
        return {
            "id": submission.id,
            "student_name": student_name,
            "submitted_at": submission.submitted_at,
            "is_anonymous": submission.is_anonymous,
            "answers": [
                {
                    "question_text": q.question_text,
                    "question_type": q.question_type.value,
                    "answer_text": a.answer_text,
                    "answer_value": a.answer_value,
                    "answer_choices": a.answer_choices
                }
                for a, q in answers
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get submission details error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch submission details")

@router.get("/forms/{form_id}/analytics")
async def get_form_analytics(
    form_id: int,
    current_user = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Get aggregated analytics for a feedback form (Staff only)"""
    try:
        if not is_staff(current_user):
            raise HTTPException(status_code=403, detail="Only staff can view analytics")
        
        form = db.query(FeedbackForm).filter(FeedbackForm.id == form_id).first()
        if not form:
            raise HTTPException(status_code=404, detail="Feedback form not found")
        
        questions = db.query(FeedbackQuestion).filter(
            FeedbackQuestion.form_id == form_id
        ).order_by(FeedbackQuestion.order_index).all()
        
        total_submissions = db.query(func.count(FeedbackSubmission.id)).filter(
            FeedbackSubmission.form_id == form_id
        ).scalar()
        
        analytics = []
        for question in questions:
            answers = db.query(FeedbackAnswer).filter(
                FeedbackAnswer.question_id == question.id
            ).all()
            
            if question.question_type == QuestionType.RATING:
                # Calculate average rating
                ratings = [a.answer_value for a in answers if a.answer_value is not None]
                avg_rating = sum(ratings) / len(ratings) if ratings else 0
                analytics.append({
                    "question_text": question.question_text,
                    "question_type": "RATING",
                    "average_rating": round(avg_rating, 2),
                    "total_responses": len(ratings)
                })
            elif question.question_type == QuestionType.MULTIPLE_CHOICE:
                # Count choices
                choice_counts = {}
                for answer in answers:
                    if answer.answer_text:
                        choice_counts[answer.answer_text] = choice_counts.get(answer.answer_text, 0) + 1
                analytics.append({
                    "question_text": question.question_text,
                    "question_type": "MULTIPLE_CHOICE",
                    "choice_distribution": choice_counts,
                    "total_responses": len(answers)
                })
            else:
                # Text responses
                responses = [a.answer_text for a in answers if a.answer_text]
                analytics.append({
                    "question_text": question.question_text,
                    "question_type": question.question_type.value,
                    "responses": responses,
                    "total_responses": len(responses)
                })
        
        return {
            "form_title": form.title,
            "total_submissions": total_submissions,
            "analytics": analytics
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get form analytics error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch analytics")
