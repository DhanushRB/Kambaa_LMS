from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, SessionContent
from cohort_specific_models import CohortSessionContent, CohortCourseSession
from auth import get_current_admin_or_presenter
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/debug", tags=["Debug"])

@router.get("/session/{session_id}/content-debug")
async def debug_session_content(
    session_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Debug endpoint to show all content from both regular and cohort sessions"""
    try:
        debug_info = {
            "session_id": session_id,
            "regular_session_content": [],
            "cohort_session_content": [],
            "is_cohort_session": False,
            "session_exists": False,
            "cohort_session_exists": False
        }
        
        # Check if regular session exists
        from database import Session as RegularSession
        regular_session = db.query(RegularSession).filter(RegularSession.id == session_id).first()
        debug_info["session_exists"] = regular_session is not None
        
        # Check if cohort session exists
        cohort_session = db.query(CohortCourseSession).filter(CohortCourseSession.id == session_id).first()
        debug_info["cohort_session_exists"] = cohort_session is not None
        debug_info["is_cohort_session"] = cohort_session is not None
        
        # Get regular session content
        regular_contents = db.query(SessionContent).filter(SessionContent.session_id == session_id).all()
        for content in regular_contents:
            debug_info["regular_session_content"].append({
                "id": content.id,
                "content_type": content.content_type,
                "title": content.title,
                "description": content.description,
                "meeting_url": content.meeting_url,
                "scheduled_time": content.scheduled_time.isoformat() if content.scheduled_time else None,
                "created_at": content.created_at.isoformat() if content.created_at else None,
                "uploaded_by": content.uploaded_by
            })
        
        # Get cohort session content
        cohort_contents = db.query(CohortSessionContent).filter(CohortSessionContent.session_id == session_id).all()
        for content in cohort_contents:
            debug_info["cohort_session_content"].append({
                "id": content.id,
                "content_type": content.content_type,
                "title": content.title,
                "description": content.description,
                "meeting_url": content.meeting_url,
                "scheduled_time": content.scheduled_time.isoformat() if content.scheduled_time else None,
                "created_at": content.created_at.isoformat() if content.created_at else None,
                "uploaded_by": content.uploaded_by
            })
        
        # Summary
        debug_info["summary"] = {
            "total_regular_content": len(debug_info["regular_session_content"]),
            "total_cohort_content": len(debug_info["cohort_session_content"]),
            "regular_meeting_links": len([c for c in debug_info["regular_session_content"] if c["content_type"] == "MEETING_LINK"]),
            "cohort_meeting_links": len([c for c in debug_info["cohort_session_content"] if c["content_type"] == "MEETING_LINK"])
        }
        
        return debug_info
        
    except Exception as e:
        logger.error(f"Debug session content error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")

@router.get("/all-sessions-summary")
async def debug_all_sessions_summary(
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get a summary of all sessions and their content"""
    try:
        from database import Session as RegularSession
        
        summary = {
            "regular_sessions": [],
            "cohort_sessions": [],
            "total_regular_content": 0,
            "total_cohort_content": 0,
            "total_meeting_links": 0
        }
        
        # Get all regular sessions
        regular_sessions = db.query(RegularSession).all()
        for session in regular_sessions:
            content_count = db.query(SessionContent).filter(SessionContent.session_id == session.id).count()
            meeting_count = db.query(SessionContent).filter(
                SessionContent.session_id == session.id,
                SessionContent.content_type == "MEETING_LINK"
            ).count()
            
            summary["regular_sessions"].append({
                "id": session.id,
                "title": session.title,
                "content_count": content_count,
                "meeting_links": meeting_count
            })
            summary["total_regular_content"] += content_count
            summary["total_meeting_links"] += meeting_count
        
        # Get all cohort sessions
        cohort_sessions = db.query(CohortCourseSession).all()
        for session in cohort_sessions:
            content_count = db.query(CohortSessionContent).filter(CohortSessionContent.session_id == session.id).count()
            meeting_count = db.query(CohortSessionContent).filter(
                CohortSessionContent.session_id == session.id,
                CohortSessionContent.content_type == "MEETING_LINK"
            ).count()
            
            summary["cohort_sessions"].append({
                "id": session.id,
                "title": session.title,
                "content_count": content_count,
                "meeting_links": meeting_count
            })
            summary["total_cohort_content"] += content_count
            summary["total_meeting_links"] += meeting_count
        
        return summary
        
    except Exception as e:
        logger.error(f"Debug all sessions summary error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")

@router.post("/test-meeting-creation/{session_id}")
async def test_meeting_creation(
    session_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Test creating a meeting link for debugging"""
    try:
        from datetime import datetime, timedelta
        
        # Test data
        test_meeting = {
            "session_id": session_id,
            "content_type": "MEETING_LINK",
            "title": "Debug Test Meeting",
            "description": "This is a test meeting created for debugging",
            "meeting_url": "https://zoom.us/j/debug123456",
            "scheduled_time": datetime.now() + timedelta(hours=1)
        }
        
        # Check if it's a cohort session
        cohort_session = db.query(CohortCourseSession).filter(CohortCourseSession.id == session_id).first()
        
        if cohort_session:
            # Create cohort session content
            content = CohortSessionContent(
                session_id=session_id,
                content_type=test_meeting["content_type"],
                title=test_meeting["title"],
                description=test_meeting["description"],
                meeting_url=test_meeting["meeting_url"],
                scheduled_time=test_meeting["scheduled_time"],
                uploaded_by=current_user.id
            )
            db.add(content)
            db.commit()
            db.refresh(content)
            
            return {
                "message": "Test meeting created successfully in cohort session content",
                "content_id": content.id,
                "session_type": "cohort",
                "test_data": test_meeting
            }
        else:
            # Create regular session content
            content = SessionContent(
                session_id=session_id,
                content_type=test_meeting["content_type"],
                title=test_meeting["title"],
                description=test_meeting["description"],
                meeting_url=test_meeting["meeting_url"],
                scheduled_time=test_meeting["scheduled_time"],
                uploaded_by=current_user.id
            )
            db.add(content)
            db.commit()
            db.refresh(content)
            
            return {
                "message": "Test meeting created successfully in regular session content",
                "content_id": content.id,
                "session_type": "regular",
                "test_data": test_meeting
            }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Test meeting creation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")