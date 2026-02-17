from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import get_db, User, SessionModel, Module, Resource, Enrollment
from auth import get_current_user
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/student", tags=["student_resources"])

# Import logging functions
from main import log_student_action

@router.get("/session/{session_id}/resources")
async def get_student_session_resources(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get session resources for students - serves downloaded files, not original links"""
    try:
        # Check if student is enrolled in the course containing this session
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        module = db.query(Module).filter(Module.id == session.module_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        
        # Check enrollment
        enrollment = db.query(Enrollment).filter(
            Enrollment.student_id == current_user.id,
            Enrollment.course_id == module.course_id
        ).first()
        
        if not enrollment:
            raise HTTPException(status_code=403, detail="Not enrolled in this course")
        
        # Get resources
        resources = db.query(Resource).filter(Resource.session_id == session_id).all()
        
        result = []
        for resource in resources:
            # Only show resources with existing files
            if resource.file_path and os.path.exists(resource.file_path):
                filename = os.path.basename(resource.file_path)
                
                result.append({
                    "id": resource.id,
                    "title": resource.title,
                    "resource_type": resource.resource_type,
                    "filename": filename,
                    "file_size": resource.file_size,
                    "description": resource.description,
                    "download_url": f"/api/resources/{filename}",
                    "uploaded_at": resource.uploaded_at
                })
        
        # Log student resource access
        log_student_action(
            student_id=current_user.id,
            student_username=current_user.username,
            action_type="VIEW",
            resource_type="SESSION_RESOURCES",
            resource_id=session_id,
            details=f"Accessed resources for session: {session.title}"
        )
        
        return {"resources": result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get student session resources error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch resources")

@router.get("/resource/{resource_id}/download")
async def download_student_resource(
    resource_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download a specific resource file for students"""
    try:
        resource = db.query(Resource).filter(Resource.id == resource_id).first()
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        # Check if student has access to this resource
        session = db.query(SessionModel).filter(SessionModel.id == resource.session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        module = db.query(Module).filter(Module.id == session.module_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        
        # Check enrollment
        enrollment = db.query(Enrollment).filter(
            Enrollment.student_id == current_user.id,
            Enrollment.course_id == module.course_id
        ).first()
        
        if not enrollment:
            raise HTTPException(status_code=403, detail="Not enrolled in this course")
        
        # Check if file exists
        if not resource.file_path or not os.path.exists(resource.file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Log student resource download
        log_student_action(
            student_id=current_user.id,
            student_username=current_user.username,
            action_type="DOWNLOAD",
            resource_type="RESOURCE",
            resource_id=resource_id,
            details=f"Downloaded resource: {resource.title}"
        )
        
        # Serve the file
        filename = os.path.basename(resource.file_path)
        return FileResponse(
            resource.file_path,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download student resource error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download resource")