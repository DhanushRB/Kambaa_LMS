from fastapi import APIRouter, HTTPException, Depends, Form, UploadFile, File
from sqlalchemy.orm import Session
from database import get_db, SessionModel, Quiz, QuizAttempt, Module, Course
from auth import get_current_admin_or_presenter, get_current_presenter
from typing import Optional
import logging
import json

router = APIRouter(prefix="/admin", tags=["Quiz Management"])
logger = logging.getLogger(__name__)

# Quiz Management Endpoints
@router.post("/sessions/{session_id}/quizzes")
async def create_quiz(
    session_id: int,
    title: str = Form(...),
    description: str = Form(...),
    total_marks: int = Form(...),
    time_limit_minutes: int = Form(60),
    questions: str = Form(...),
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Create a new quiz for a session"""
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        quiz = Quiz(
            session_id=session_id,
            title=title,
            description=description,
            total_marks=total_marks,
            time_limit_minutes=time_limit_minutes,
            questions=questions,
            is_active=True
        )
        
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
        
        return {"message": "Quiz created successfully", "quiz_id": quiz.id}
    except Exception as e:
        db.rollback()
        logger.error(f"Create quiz error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create quiz")

@router.get("/sessions/{session_id}/quizzes")
async def get_session_quizzes(
    session_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get all quizzes for a session"""
    try:
        quizzes = db.query(Quiz).filter(Quiz.session_id == session_id).all()
        
        result = []
        for quiz in quizzes:
            attempts_count = db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz.id).count()
            
            result.append({
                "id": quiz.id,
                "title": quiz.title,
                "description": quiz.description,
                "total_marks": quiz.total_marks,
                "time_limit_minutes": quiz.time_limit_minutes,
                "is_active": quiz.is_active,
                "attempts_count": attempts_count,
                "created_at": quiz.created_at
            })
        
        return {"quizzes": result}
    except Exception as e:
        logger.error(f"Get session quizzes error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch quizzes")

@router.put("/quizzes/{quiz_id}")
async def update_quiz(
    quiz_id: int,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    total_marks: Optional[int] = Form(None),
    time_limit_minutes: Optional[int] = Form(None),
    questions: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Update a quiz"""
    try:
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        
        if title is not None:
            quiz.title = title
        if description is not None:
            quiz.description = description
        if total_marks is not None:
            quiz.total_marks = total_marks
        if time_limit_minutes is not None:
            quiz.time_limit_minutes = time_limit_minutes
        if questions is not None:
            quiz.questions = questions
        if is_active is not None:
            quiz.is_active = is_active
        
        db.commit()
        
        return {"message": "Quiz updated successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Update quiz error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update quiz")

@router.delete("/quizzes/{quiz_id}")
async def delete_quiz(
    quiz_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Delete a quiz"""
    try:
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        
        # Delete quiz attempts first
        db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz_id).delete()
        
        # Delete the quiz
        db.delete(quiz)
        db.commit()
        
        return {"message": "Quiz deleted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Delete quiz error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete quiz")

@router.get("/quizzes/{quiz_id}/attempts")
async def get_quiz_attempts(
    quiz_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get all attempts for a quiz"""
    try:
        attempts = db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz_id).all()
        
        result = []
        for attempt in attempts:
            result.append({
                "id": attempt.id,
                "student_id": attempt.student_id,
                "score": attempt.score,
                "time_taken_minutes": attempt.time_taken_minutes,
                "attempted_at": attempt.attempted_at
            })
        
        return {"attempts": result}
    except Exception as e:
        logger.error(f"Get quiz attempts error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch quiz attempts")

# AI Quiz Generation
@router.post("/sessions/{session_id}/generate-quiz")
async def generate_ai_quiz(
    session_id: int,
    title: str = Form(...),
    content: str = Form(...),
    question_type: str = Form(...),
    num_questions: int = Form(...),
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Generate quiz using AI"""
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Import quiz generator
        try:
            from quiz_generator import generate_quiz_questions
            questions = generate_quiz_questions(content, question_type, num_questions)
        except ImportError:
            questions = []
        
        if not questions:
            raise HTTPException(status_code=500, detail="Failed to generate quiz questions")
        
        # Create quiz with generated questions
        quiz = Quiz(
            session_id=session_id,
            title=title,
            description=f"AI-generated {question_type} quiz",
            total_marks=len(questions) * 10,  # 10 marks per question
            time_limit_minutes=max(30, len(questions) * 2),  # 2 minutes per question, minimum 30
            questions=json.dumps(questions),
            is_active=True
        )
        
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
        
        return {
            "message": "AI quiz generated successfully",
            "quiz_id": quiz.id,
            "questions_count": len(questions)
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Generate AI quiz error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate AI quiz")

@router.post("/sessions/{session_id}/quiz-from-file")
async def create_quiz_from_file(
    session_id: int,
    file: UploadFile = File(...),
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Create quiz from uploaded file content"""
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Read file content
        content = await file.read()
        file_content = content.decode('utf-8')
        
        # Generate questions from file content
        try:
            from quiz_generator import generate_quiz_questions
            questions = generate_quiz_questions(file_content, "MCQ", 10)
        except ImportError:
            questions = []
        
        if not questions:
            raise HTTPException(status_code=500, detail="Failed to generate quiz from file")
        
        # Create quiz
        quiz = Quiz(
            session_id=session_id,
            title=f"Quiz from {file.filename}",
            description=f"Quiz generated from uploaded file: {file.filename}",
            total_marks=len(questions) * 10,
            time_limit_minutes=max(30, len(questions) * 2),
            questions=json.dumps(questions),
            is_active=True
        )
        
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
        
        return {
            "message": "Quiz created from file successfully",
            "quiz_id": quiz.id,
            "questions_count": len(questions)
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Create quiz from file error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create quiz from file")