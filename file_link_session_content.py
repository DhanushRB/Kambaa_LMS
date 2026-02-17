from fastapi import APIRouter, HTTPException, Depends, Form
from sqlalchemy.orm import Session
from database import get_db, SessionContent, Session as SessionModel
from auth import get_current_admin_or_presenter
from typing import Optional
import logging

router = APIRouter(prefix="/admin", tags=["File Links"])
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["File Links"])
logger = logging.getLogger(__name__)

@router.post("/sessions/{session_id}/file-link")
async def add_file_link(
    session_id: int,
    title: str = Form(...),
    file_url: str = Form(...),
    description: Optional[str] = Form(None),
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Add external file link (Google Drive, Teams, etc.) to session content"""
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Store as external link
        content = SessionContent(
            session_id=session_id,
            content_type="EXTERNAL_LINK",
            title=title,
            description=description,
            file_path=file_url,
            file_type="external_link",
            file_size=0,
            uploaded_by=current_user.id
        )
        
        db.add(content)
        db.commit()
        db.refresh(content)
        
        return {
            "message": "External link added successfully",
            "content_id": content.id,
            "file_url": file_url
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Add file link error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to add file link")

@router.get("/session-content/{content_id}/view")
async def view_session_content(
    content_id: int,
    db: Session = Depends(get_db)
):
    """View or get external link for session content"""
    try:
        content = db.query(SessionContent).filter(SessionContent.id == content_id).first()
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")
        
        if content.content_type == "EXTERNAL_LINK":
            return {
                "type": "external_link",
                "url": content.file_path,
                "title": content.title,
                "description": content.description,
                "message": "Open this link in a new tab to view the file"
            }
        
        return {
            "type": "file",
            "content_type": content.content_type,
            "title": content.title,
            "file_path": content.file_path,
            "file_type": content.file_type
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"View session content error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to view content")
