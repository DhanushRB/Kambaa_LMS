from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import get_db, Resource
from pathlib import Path
from typing import Optional
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["file_serving"])

UPLOAD_BASE_DIR = Path("uploads")

@router.get("/resources/{filename}")
async def serve_resource(filename: str, request: Request, db: Session = get_db):
    """Serve uploaded resource files with proper content types for browser viewing"""
    file_path = UPLOAD_BASE_DIR / "resources" / filename
    if file_path.exists():
        # Track resource view by filename
        try:
            from resource_analytics_models import ResourceView
            resource = db.query(Resource).filter(Resource.file_path.contains(filename)).first()
            if resource:
                client_ip = request.client.host if request.client else "127.0.0.1"
                user_agent = request.headers.get("user-agent", "")
                
                view_record = ResourceView(
                    resource_id=resource.id,
                    student_id=None,
                    viewed_at=datetime.utcnow(),
                    ip_address=client_ip,
                    user_agent=user_agent
                )
                
                db.add(view_record)
                db.commit()
                logger.info(f"Resource file view tracked: resource_id={resource.id}, filename={filename}")
        except Exception as track_error:
            logger.warning(f"Failed to track resource file view: {str(track_error)}")
    
    if file_path.exists():
        file_ext = os.path.splitext(filename)[1].lower()
        
        headers = {
            "Content-Disposition": "inline; filename=\"" + filename + "\"",
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "Accept-Ranges": "bytes"
        }
        
        # Set proper MIME types for browser viewing
        if file_ext == ".pdf":
            media_type = "application/pdf"
        elif file_ext in [".txt", ".text"]:
            media_type = "text/plain; charset=utf-8"
        elif file_ext in [".html", ".htm"]:
            media_type = "text/html; charset=utf-8"
        elif file_ext in [".css"]:
            media_type = "text/css; charset=utf-8"
        elif file_ext in [".js"]:
            media_type = "application/javascript; charset=utf-8"
        elif file_ext in [".json"]:
            media_type = "application/json; charset=utf-8"
        elif file_ext in [".xml"]:
            media_type = "application/xml; charset=utf-8"
        elif file_ext in [".jpg", ".jpeg"]:
            media_type = "image/jpeg"
        elif file_ext == ".png":
            media_type = "image/png"
        elif file_ext == ".gif":
            media_type = "image/gif"
        elif file_ext == ".svg":
            media_type = "image/svg+xml"
        elif file_ext in [".mp4"]:
            media_type = "video/mp4"
        elif file_ext in [".webm"]:
            media_type = "video/webm"
        elif file_ext in [".mp3"]:
            media_type = "audio/mpeg"
        elif file_ext in [".wav"]:
            media_type = "audio/wav"
        elif file_ext in [".ogg"]:
            media_type = "audio/ogg"
        elif file_ext in [".ppt", ".pptx"]:
            media_type = "application/vnd.ms-powerpoint" if file_ext == ".ppt" else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            headers["Content-Disposition"] = "inline; filename=\"" + filename + "\""
        elif file_ext in [".doc", ".docx"]:
            media_type = "application/msword" if file_ext == ".doc" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            headers["Content-Disposition"] = "inline; filename=\"" + filename + "\""
        elif file_ext in [".xls", ".xlsx"]:
            media_type = "application/vnd.ms-excel" if file_ext == ".xls" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            headers["Content-Disposition"] = "inline; filename=\"" + filename + "\""
        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    f.read(100)
                media_type = "text/plain; charset=utf-8"
            except:
                media_type = "application/octet-stream"
                headers["Content-Disposition"] = "inline; filename=\"" + filename + "\""
        
        return FileResponse(file_path, media_type=media_type, headers=headers)
    raise HTTPException(status_code=404, detail="File not found")

@router.get("/resources/{resource_id}/view")
async def view_resource_authenticated(
    resource_id: int,
    token: Optional[str] = None,
    db: Session = get_db
):
    """View a specific resource file with authentication"""
    try:
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        from auth import get_current_user_from_token
        current_user = get_current_user_from_token(token, db)
        
        resource = db.query(Resource).filter(Resource.id == resource_id).first()
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        if not resource.file_path or not os.path.exists(resource.file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        filename = os.path.basename(resource.file_path)
        file_ext = os.path.splitext(filename)[1].lower()
        
        headers = {
            "Content-Disposition": "inline; filename=\"" + filename + "\"",
            "Cache-Control": "public, max-age=3600",
            "Accept-Ranges": "bytes"
        }
        
        if file_ext == ".pdf":
            media_type = "application/pdf"
        elif file_ext in [".txt", ".text"]:
            media_type = "text/plain; charset=utf-8"
        elif file_ext in [".jpg", ".jpeg"]:
            media_type = "image/jpeg"
        elif file_ext == ".png":
            media_type = "image/png"
        elif file_ext in [".mp4"]:
            media_type = "video/mp4"
        elif file_ext in [".ppt", ".pptx"]:
            media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        else:
            media_type = "application/octet-stream"
            
        return FileResponse(resource.file_path, media_type=media_type, headers=headers)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"View resource error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to view resource")

@router.get("/recordings/{filename}")
async def serve_recording(filename: str):
    """Serve uploaded recording files with inline viewing"""
    file_path = UPLOAD_BASE_DIR / "recordings" / filename
    if file_path.exists():
        file_ext = os.path.splitext(filename)[1].lower()
        
        headers = {
            "Content-Disposition": "inline; filename=\"" + filename + "\"",
            "Cache-Control": "public, max-age=3600",
            "Accept-Ranges": "bytes"
        }
        
        if file_ext in [".mp4"]:
            media_type = "video/mp4"
        elif file_ext in [".webm"]:
            media_type = "video/webm"
        elif file_ext in [".avi"]:
            media_type = "video/x-msvideo"
        elif file_ext in [".mov"]:
            media_type = "video/quicktime"
        elif file_ext in [".mp3"]:
            media_type = "audio/mpeg"
        elif file_ext in [".wav"]:
            media_type = "audio/wav"
        else:
            media_type = "application/octet-stream"
            
        return FileResponse(file_path, media_type=media_type, headers=headers)
    raise HTTPException(status_code=404, detail="Recording not found")

@router.get("/certificates/{filename}")
async def serve_certificate(filename: str):
    """Serve generated certificate files with inline viewing"""
    file_path = UPLOAD_BASE_DIR / "certificates" / filename
    if file_path.exists():
        headers = {
            "Content-Disposition": "inline; filename=\"" + filename + "\"",
            "Cache-Control": "public, max-age=3600"
        }
        
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext == ".pdf":
            media_type = "application/pdf"
        elif file_ext in [".jpg", ".jpeg"]:
            media_type = "image/jpeg"
        elif file_ext == ".png":
            media_type = "image/png"
        else:
            media_type = "application/octet-stream"
            
        return FileResponse(file_path, media_type=media_type, headers=headers)
    raise HTTPException(status_code=404, detail="Certificate not found")