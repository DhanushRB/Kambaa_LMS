from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db, SessionContent
from cohort_specific_models import CohortSessionContent, CohortCourseSession
from auth import get_current_admin_or_presenter
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Session Content"])

@router.get("/sessions/{session_id}/content")
async def get_session_content(
    session_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_or_presenter)
):
    """Get all session content including meeting links from both regular and cohort sessions"""
    try:
        result = []
        
        # Check if it's a cohort session first
        cohort_session = db.query(CohortCourseSession).filter(CohortCourseSession.id == session_id).first()
        
        if cohort_session:
            # Get cohort session content
            cohort_contents = db.query(CohortSessionContent).filter(
                CohortSessionContent.session_id == session_id
            ).order_by(CohortSessionContent.created_at.desc()).all()
            
            for content in cohort_contents:
                result.append({
                    "id": content.id,
                    "session_id": content.session_id,
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
        else:
            # Get regular session content
            contents = db.query(SessionContent).filter(
                SessionContent.session_id == session_id
            ).order_by(SessionContent.created_at.desc()).all()
            
            for content in contents:
                result.append({
                    "id": content.id,
                    "session_id": content.session_id,
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
        
        return {"contents": result}
        
    except Exception as e:
        logger.error(f"Failed to get session content: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch session content")

@router.get("/session-content/{session_id}")
async def get_session_content_alt(
    session_id: int,
    db: Session = Depends(get_db)
):
    """Alternative endpoint for session content (no auth required for testing)"""
    try:
        contents = db.query(SessionContent).filter(
            SessionContent.session_id == session_id
        ).order_by(SessionContent.created_at.desc()).all()
        
        result = []
        for content in contents:
            result.append({
                "id": content.id,
                "session_id": content.session_id,
                "content_type": content.content_type,
                "title": content.title,
                "description": content.description,
                "file_path": content.file_path,
                "file_type": content.file_type,
                "file_size": content.file_size,
                "meeting_url": content.meeting_url,
                "scheduled_time": content.scheduled_time.isoformat() if content.scheduled_time else None,
                "created_at": content.created_at.isoformat() if content.created_at else None,
                "uploaded_by": content.uploaded_by
            })
        
        return {"contents": result}
        
    except Exception as e:
        logger.error(f"Failed to get session content: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch session content")