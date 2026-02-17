from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db, SessionContent

router = APIRouter(prefix="/api", tags=["Debug"])

@router.get("/debug/session/{session_id}/content")
async def debug_session_content(session_id: int, db: Session = Depends(get_db)):
    """Debug endpoint to check session content"""
    try:
        contents = db.query(SessionContent).filter(
            SessionContent.session_id == session_id
        ).all()
        
        result = []
        for content in contents:
            result.append({
                "id": content.id,
                "session_id": content.session_id,
                "content_type": content.content_type,
                "title": content.title,
                "meeting_url": content.meeting_url,
                "scheduled_time": str(content.scheduled_time) if content.scheduled_time else None,
                "created_at": str(content.created_at) if content.created_at else None
            })
        
        return {
            "session_id": session_id,
            "total_contents": len(contents),
            "contents": result
        }
        
    except Exception as e:
        return {"error": str(e), "session_id": session_id}