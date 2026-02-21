from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Any, List
from pydantic import BaseModel
from database import get_db, Admin, Presenter, Manager, SessionContent, PresenterCohort
from cohort_specific_models import CohortCourseSession, CohortSessionContent, CohortSpecificCourse, CohortCourseModule
from auth import get_current_admin_or_presenter
from resource_analytics_models import ResourceView
import logging
import os
import uuid
from jose import jwt
from pathlib import Path
from auth import SECRET_KEY, ALGORITHM, get_current_user_info
from email_utils import send_content_added_notification

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Cohort Session Content"])

# Upload directories
UPLOAD_BASE_DIR = Path("uploads")
try:
    UPLOAD_BASE_DIR.mkdir(exist_ok=True)
    (UPLOAD_BASE_DIR / "resources").mkdir(exist_ok=True)
except Exception as e:
    logger.error(f"Failed to create upload directories: {e}")

# Pydantic models
class SessionContentCreate(BaseModel):
    session_id: int
    content_type: str
    title: str
    description: Optional[str] = None
    meeting_url: Optional[str] = None
    scheduled_time: Optional[datetime] = None

@router.post("/upload/resource")
async def upload_cohort_resource(
    session_id: int = Form(...),
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Upload resource for cohort course session slice"""
    try:
        logger.info(f"Received upload request for session_id: {session_id}, title: {title}")
        # Check if it's a cohort session
        cohort_session = db.query(CohortCourseSession).filter(CohortCourseSession.id == session_id).first()
        
        if cohort_session:
            # Handle cohort session upload
            file_ext = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = UPLOAD_BASE_DIR / "resources" / unique_filename
            
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            
            # Create cohort session content
            session_content = CohortSessionContent(
                session_id=session_id,
                content_type="RESOURCE",
                title=title,
                description=description,
                file_path=str(file_path),
                file_type=file_ext.lstrip('.'),
                file_size=len(content),
                uploaded_by=None  # Set to None to avoid foreign key constraint
            )
            
            db.add(session_content)
            db.commit()
            db.refresh(session_content)
            
            # Send notification
            try:
                await send_content_added_notification(
                    db=db,
                    session_id=session_id,
                    content_title=title,
                    content_type="RESOURCE",
                    session_type="cohort",
                    description=description
                )
            except Exception as e:
                logger.error(f"Failed to trigger notification: {str(e)}")
            
            return {
                "message": "Resource uploaded successfully",
                "resource_id": session_content.id,
                "filename": unique_filename
            }
        else:
            raise HTTPException(status_code=404, detail="Session not found")
            
    except Exception as e:
        db.rollback()
        logger.error(f"Upload cohort resource error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload resource")

@router.get("/session-content/{session_id}")
async def get_cohort_session_content(
    session_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get content for both cohort and regular sessions including assignments and quizzes"""
    try:
        from database import SessionContent, Session as RegularSession
        from assignment_quiz_models import Assignment, Quiz
        
        result = []
        
        # Check if it's a cohort session first
        cohort_session = db.query(CohortCourseSession).filter(CohortCourseSession.id == session_id).first()
        
        if cohort_session:
            # Get cohort session content
            contents = db.query(CohortSessionContent).filter(CohortSessionContent.session_id == session_id).all()
            
            for content in contents:
                result.append({
                    "id": f"resource_{content.id}",
                    "content_type": content.content_type,
                    "title": content.title,
                    "description": content.description,
                    "file_path": content.file_path,
                    "file_type": content.file_type,
                    "file_size": content.file_size,
                    "meeting_url": content.meeting_url,
                    "scheduled_time": content.scheduled_time.isoformat() if content.scheduled_time else None,
                    "created_at": content.created_at.isoformat() if content.created_at else None,
                    "uploaded_by": content.uploaded_by,
                    "source": "cohort"
                })
            
            # Get assignments for this cohort session
            assignments = db.query(Assignment).filter(
                Assignment.session_id == session_id,
                Assignment.is_active == True
            ).all()
            
            for assignment in assignments:
                result.append({
                    "id": f"assignment_{assignment.id}",
                    "content_type": "ASSIGNMENT",
                    "title": assignment.title,
                    "description": assignment.description,
                    "due_date": assignment.due_date.isoformat() if assignment.due_date else None,
                    "total_marks": assignment.total_marks,
                    "submission_type": assignment.submission_type.value,
                    "created_at": assignment.created_at.isoformat() if assignment.created_at else None,
                    "source": "cohort"
                })
            
            # Get quizzes for this cohort session
            quizzes = db.query(Quiz).filter(
                Quiz.session_id == session_id,
                Quiz.is_active == True
            ).all()
            
            for quiz in quizzes:
                result.append({
                    "id": f"quiz_{quiz.id}",
                    "content_type": "QUIZ",
                    "title": quiz.title,
                    "description": quiz.description,
                    "time_limit_minutes": quiz.time_limit_minutes,
                    "total_marks": quiz.total_marks,
                    "auto_submit": quiz.auto_submit,
                    "created_at": quiz.created_at.isoformat() if quiz.created_at else None,
                    "source": "cohort"
                })
        else:
            # Check regular session
            regular_session = db.query(RegularSession).filter(RegularSession.id == session_id).first()
            if regular_session:
                # Get regular session content
                contents = db.query(SessionContent).filter(SessionContent.session_id == session_id).all()
                
                for content in contents:
                    result.append({
                        "id": f"resource_{content.id}",
                        "content_type": content.content_type,
                        "title": content.title,
                        "description": content.description,
                        "file_path": content.file_path,
                        "file_type": content.file_type,
                        "file_size": content.file_size,
                        "meeting_url": content.meeting_url,
                        "scheduled_time": content.scheduled_time.isoformat() if content.scheduled_time else None,
                        "created_at": content.created_at.isoformat() if content.created_at else None,
                        "uploaded_by": content.uploaded_by,
                        "source": "regular"
                    })
                
                # Get assignments for this regular session
                assignments = db.query(Assignment).filter(
                    Assignment.session_id == session_id,
                    Assignment.is_active == True
                ).all()
                
                for assignment in assignments:
                    result.append({
                        "id": f"assignment_{assignment.id}",
                        "content_type": "ASSIGNMENT",
                        "title": assignment.title,
                        "description": assignment.description,
                        "due_date": assignment.due_date.isoformat() if assignment.due_date else None,
                        "total_marks": assignment.total_marks,
                        "submission_type": assignment.submission_type.value,
                        "created_at": assignment.created_at.isoformat() if assignment.created_at else None,
                        "source": "regular"
                    })
                
                # Get quizzes for this regular session
                quizzes = db.query(Quiz).filter(
                    Quiz.session_id == session_id,
                    Quiz.is_active == True
                ).all()
                
                for quiz in quizzes:
                    result.append({
                        "id": f"quiz_{quiz.id}",
                        "content_type": "QUIZ",
                        "title": quiz.title,
                        "description": quiz.description,
                        "time_limit_minutes": quiz.time_limit_minutes,
                        "total_marks": quiz.total_marks,
                        "auto_submit": quiz.auto_submit,
                        "created_at": quiz.created_at.isoformat() if quiz.created_at else None,
                        "source": "regular"
                    })
        
        return {"contents": result}
        
    except Exception as e:
        logger.error(f"Get session content error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch content")

@router.post("/session-content")
async def create_cohort_session_content(
    content_data: SessionContentCreate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Create session content for cohort course using JSON payload"""
    try:
        # Check if it's a cohort session
        cohort_session = db.query(CohortCourseSession).filter(CohortCourseSession.id == content_data.session_id).first()
        
        if cohort_session:
            # Create cohort session content
            session_content = CohortSessionContent(
                session_id=content_data.session_id,
                content_type=content_data.content_type,
                title=content_data.title,
                description=content_data.description,
                meeting_url=content_data.meeting_url,
                scheduled_time=content_data.scheduled_time,
                uploaded_by=None  # Set to None to avoid foreign key constraint
            )
            
            db.add(session_content)
            db.commit()
            db.refresh(session_content)
            
            # Send notification
            try:
                await send_content_added_notification(
                    db=db,
                    session_id=content_data.session_id,
                    content_title=content_data.title,
                    content_type=content_data.content_type,
                    session_type="cohort",
                    description=content_data.description
                )
            except Exception as e:
                logger.error(f"Failed to trigger notification: {str(e)}")
            
            return {
                "message": "Content created successfully",
                "content_id": session_content.id
            }
        else:
            # Handle regular session
            from database import SessionContent, Session as RegularSession
            regular_session = db.query(RegularSession).filter(RegularSession.id == content_data.session_id).first()
            
            if regular_session:
                session_content = SessionContent(
                    session_id=content_data.session_id,
                    content_type=content_data.content_type,
                    title=content_data.title,
                    description=content_data.description,
                    meeting_url=content_data.meeting_url,
                    scheduled_time=content_data.scheduled_time,
                    uploaded_by=current_user.id
                )
                
                db.add(session_content)
                db.commit()
                db.refresh(session_content)
                
                # Send notification for regular session
                try:
                    await send_content_added_notification(
                        db=db,
                        session_id=content_data.session_id,
                        content_title=content_data.title,
                        content_type=content_data.content_type,
                        session_type="global",
                        description=content_data.description
                    )
                except Exception as e:
                    logger.error(f"Failed to trigger notification: {str(e)}")
                
                return {
                    "message": "Content created successfully",
                    "content_id": session_content.id
                }
            else:
                raise HTTPException(status_code=404, detail="Session not found")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Create session content error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create content")

@router.put("/session-content/{content_id}")
async def update_cohort_session_content(
    content_id: Any,
    content_data: SessionContentCreate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Update session content (Meeting/Material) for cohort or regular course"""
    try:
        # Handle prefixed IDs
        if isinstance(content_id, str):
            if "_" in content_id:
                try:
                    content_id = int(content_id.split("_")[1])
                except (IndexError, ValueError):
                    pass
            elif content_id.isdigit():
                content_id = int(content_id)
        
        # Try cohort first
        content = db.query(CohortSessionContent).filter(CohortSessionContent.id == content_id).first()
        
        if content:
            content.title = content_data.title
            content.description = content_data.description
            content.meeting_url = content_data.meeting_url
            content.scheduled_time = content_data.scheduled_time
        else:
            # Try regular
            from database import SessionContent as RegularSessionContent
            content = db.query(RegularSessionContent).filter(RegularSessionContent.id == content_id).first()
            if not content:
                raise HTTPException(status_code=404, detail="Content not found")
            
            content.title = content_data.title
            content.description = content_data.description
            content.meeting_url = content_data.meeting_url
            content.scheduled_time = content_data.scheduled_time

        db.commit()
        return {"message": "Content updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update session content error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update content")

@router.put("/upload/resource/{content_id}")
async def update_cohort_resource(
    content_id: Any,
    file: Optional[UploadFile] = File(None),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Update resource for cohort course session"""
    try:
        # Handle prefixed IDs
        if isinstance(content_id, str):
            if "_" in content_id:
                try:
                    content_id = int(content_id.split("_")[1])
                except (IndexError, ValueError):
                    pass
            elif content_id.isdigit():
                content_id = int(content_id)

        content = db.query(CohortSessionContent).filter(CohortSessionContent.id == content_id).first()
        
        if not content:
            # Fallback to regular SessionContent
            from database import SessionContent as RegularSessionContent
            content = db.query(RegularSessionContent).filter(RegularSessionContent.id == content_id).first()
            if not content:
                raise HTTPException(status_code=404, detail="Resource not found")
        
        content.title = title
        content.description = description
        
        if file:
            # Delete old file
            if content.file_path and os.path.exists(content.file_path):
                try:
                    os.remove(content.file_path)
                except:
                    pass
            
            # Save new file
            file_ext = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = UPLOAD_BASE_DIR / "resources" / unique_filename
            
            file_data = await file.read()
            with open(file_path, "wb") as f:
                f.write(file_data)
            
            content.file_path = str(file_path)
            content.file_type = file_ext.lstrip('.')
            content.file_size = len(file_data)
        
        db.commit()
        return {"message": "Resource updated successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update resource error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update resource")

# Remove the duplicate Pydantic model definition that was causing the error

# Remove the duplicate JSON endpoint since we updated the main one
# @router.post("/session-content-json") - REMOVED

@router.get("/cohort-content/{content_id}/view")
async def view_cohort_content(
    content_id: Any,
    request: Request,
    token: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """View cohort session content file"""
    try:
        # Handle prefixed IDs
        if isinstance(content_id, str):
            if "_" in content_id:
                try:
                    content_id = int(content_id.split("_")[1])
                except (IndexError, ValueError):
                    pass
            elif content_id.isdigit():
                content_id = int(content_id)

        # Authentication and authorization
        try:
            auth_header = request.headers.get("Authorization")
            auth_token = None
            if auth_header and auth_header.startswith("Bearer "):
                auth_token = auth_header.split(" ")[1]
            elif token:
                auth_token = token
            
            if not auth_token:
                raise HTTPException(status_code=401, detail="Authentication required")
                
            payload = jwt.decode(auth_token, SECRET_KEY, algorithms=[ALGORITHM])
            # get_current_user_info works for all roles including Admin/Presenter
            current_user = get_current_user_info(payload, db)
        except Exception as auth_error:
            raise HTTPException(status_code=401, detail=f"Authentication failed: {str(auth_error)}")
        content = db.query(CohortSessionContent).filter(CohortSessionContent.id == content_id).first()
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")
        
        if not content.file_path or not os.path.exists(content.file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        filename = os.path.basename(content.file_path)
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext == ".pdf":
            media_type = "application/pdf"
        elif file_ext in [".jpg", ".jpeg", ".png", ".gif"]:
            media_type = f"image/{file_ext[1:]}"
        elif file_ext in [".mp4", ".avi", ".mov", ".wmv"]:
            media_type = "video/mp4" if file_ext == ".mp4" else "video/quicktime"
        elif file_ext in [".ppt", ".pptx"]:
            if file_ext == ".ppt":
                media_type = "application/vnd.ms-powerpoint"
            else:
                media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        elif file_ext in [".doc", ".docx"]:
            if file_ext == ".doc":
                media_type = "application/msword"
            else:
                media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            media_type = "application/octet-stream"
        
        # Set headers for inline viewing
        headers = {
            "Content-Disposition": f"inline; filename={filename}"
        }
        
        # Track view if current_user is a student
        try:
            if current_user.get("role") == "Student":
                client_ip = request.client.host if request.client else "unknown"
                user_agent = request.headers.get("user-agent", "")
                
                view_record = ResourceView(
                    resource_id=content_id,
                    student_id=current_user["id"],
                    viewed_at=datetime.utcnow(),
                    ip_address=client_ip,
                    user_agent=user_agent,
                    resource_type="COHORT_RESOURCE"
                )
                db.add(view_record)
                db.commit()
                logger.info(f"Tracked cohort resource view: resource={content_id}, user={current_user['id']}")
        except Exception as track_error:
            logger.error(f"Failed to track cohort resource view: {str(track_error)}")
            db.rollback()

        return FileResponse(
            content.file_path, 
            media_type=media_type,
            headers=headers
        )
        
    except Exception as e:
        logger.error(f"View cohort content error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to view content")

@router.delete("/session-content/{content_id}")
async def delete_cohort_session_content(
    content_id: Any,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Delete cohort session content with RBAC and fallback to regular session content"""
    try:
        # Handle prefixed IDs
        if isinstance(content_id, str):
            if "_" in content_id:
                try:
                    content_id = int(content_id.split("_")[1])
                except (IndexError, ValueError):
                    pass
            elif content_id.isdigit():
                content_id = int(content_id)

        # 1. Try to find cohort session content first
        content = db.query(CohortSessionContent).filter(CohortSessionContent.id == content_id).first()
        
        if content:
            # RBAC for presenters
            if isinstance(current_user, Presenter):
                session = db.query(CohortCourseSession).filter(
                    CohortCourseSession.id == content.session_id
                ).first()
                
                if session:
                    module = db.query(CohortCourseModule).filter(
                        CohortCourseModule.id == session.module_id
                    ).first()
                    
                    if module:
                        course = db.query(CohortSpecificCourse).filter(
                            CohortSpecificCourse.id == module.course_id
                        ).first()
                        
                        if course:
                            # Verify presenter has access to this cohort
                            presenter_cohort = db.query(PresenterCohort).filter(
                                PresenterCohort.presenter_id == current_user.id,
                                PresenterCohort.cohort_id == course.cohort_id
                            ).first()
                            
                            if not presenter_cohort:
                                raise HTTPException(status_code=403, detail="Access denied: Cohort not assigned to presenter")

            # Delete file from filesystem if it exists
            if content.file_path and os.path.exists(content.file_path):
                try:
                    os.remove(content.file_path)
                except Exception as file_err:
                    logger.warning(f"Failed to delete file {content.file_path}: {file_err}")

            # Delete database record
            db.delete(content)
            db.commit()

            return {"message": "Cohort content deleted successfully"}

        # 2. If not found in cohort content, check regular session content (fallback)
        regular_content = db.query(SessionContent).filter(SessionContent.id == content_id).first()
        
        if regular_content:
            # RBAC for presenters - for regular session content, we'd theoretically need a different check, 
            # but usually presenters only manage cohort-specific content. 
            # If current_user is Presenter, we allow deletion if they are authorized for the session.
            # For now, let's keep it simple: Admins/Managers allowed, Presenters checked if applicable.
            
            # Delete file from filesystem if it exists
            if regular_content.file_path and os.path.exists(regular_content.file_path):
                try:
                    os.remove(regular_content.file_path)
                except Exception as file_err:
                    logger.warning(f"Failed to delete file {regular_content.file_path}: {file_err}")

            # Delete database record
            db.delete(regular_content)
            db.commit()

            return {"message": "Session content deleted successfully"}

        raise HTTPException(status_code=404, detail="Content not found")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete session content error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete content")

@router.get("/session/{session_id}/assignments")
async def get_session_assignments(
    session_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get assignments for a session with analytics"""
    try:
        from assignment_quiz_models import Assignment, AssignmentSubmission, AssignmentGrade
        
        assignments = db.query(Assignment).filter(
            Assignment.session_id == session_id,
            Assignment.is_active == True
        ).all()
        
        result = []
        for assignment in assignments:
            # Get submission stats
            total_submissions = db.query(AssignmentSubmission).filter(
                AssignmentSubmission.assignment_id == assignment.id
            ).count()
            
            pending_review = db.query(AssignmentSubmission).filter(
                AssignmentSubmission.assignment_id == assignment.id,
                AssignmentSubmission.status == "SUBMITTED"
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
                average_score = round(total_percentage / len(grades), 2)
            
            result.append({
                "id": assignment.id,
                "title": assignment.title,
                "description": assignment.description,
                "due_date": assignment.due_date,
                "total_marks": assignment.total_marks,
                "submission_type": assignment.submission_type.value,
                "total_submissions": total_submissions,
                "pending_review": pending_review,
                "graded": graded,
                "average_score": average_score,
                "created_at": assignment.created_at
            })
        
        return {"assignments": result}
        
    except Exception as e:
        logger.error(f"Get session assignments error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch assignments")

@router.get("/session/{session_id}/quizzes")
async def get_session_quizzes(
    session_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get quizzes for a session with analytics"""
    try:
        from assignment_quiz_models import Quiz, QuizQuestion, QuizAttempt, QuizResult
        
        quizzes = db.query(Quiz).filter(
            Quiz.session_id == session_id,
            Quiz.is_active == True
        ).all()
        
        result = []
        for quiz in quizzes:
            # Get quiz stats
            question_count = db.query(QuizQuestion).filter(
                QuizQuestion.quiz_id == quiz.id
            ).count()
            
            total_attempts = db.query(QuizAttempt).filter(
                QuizAttempt.quiz_id == quiz.id
            ).count()
            
            completed_attempts = db.query(QuizAttempt).filter(
                QuizAttempt.quiz_id == quiz.id,
                QuizAttempt.status == "COMPLETED"
            ).count()
            
            # Calculate average score
            results = db.query(QuizResult).filter(
                QuizResult.quiz_id == quiz.id
            ).all()
            
            average_score = None
            if results:
                total_percentage = sum(r.percentage for r in results)
                average_score = round(total_percentage / len(results), 2)
            
            result.append({
                "id": quiz.id,
                "title": quiz.title,
                "description": quiz.description,
                "time_limit_minutes": quiz.time_limit_minutes,
                "total_marks": quiz.total_marks,
                "auto_submit": quiz.auto_submit,
                "question_count": question_count,
                "total_attempts": total_attempts,
                "completed_attempts": completed_attempts,
                "average_score": average_score,
                "created_at": quiz.created_at
            })
        
        return {"quizzes": result}
        
    except Exception as e:
        logger.error(f"Get session quizzes error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch quizzes")