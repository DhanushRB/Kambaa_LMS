from fastapi import APIRouter, HTTPException, Depends, Form, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db, Resource, Session as SessionModel
from auth import get_current_admin_or_presenter
import requests
import aiohttp
import aiofiles
import uuid
import os
from pathlib import Path
import logging
from urllib.parse import urlparse
import mimetypes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/resources", tags=["File Link Resources"])

# Upload directory setup
UPLOAD_BASE_DIR = Path("uploads")
UPLOAD_BASE_DIR.mkdir(exist_ok=True)
(UPLOAD_BASE_DIR / "resources").mkdir(exist_ok=True)

def get_file_type_from_url(url: str, content_type: str = None) -> str:
    """Determine file type from URL and content type"""
    try:
        # Parse URL to get file extension
        parsed_url = urlparse(url)
        file_path = parsed_url.path
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Map extensions to types
        if file_ext in ['.pdf']:
            return 'PDF'
        elif file_ext in ['.ppt', '.pptx']:
            return 'PPT'
        elif file_ext in ['.doc', '.docx']:
            return 'DOC'
        elif file_ext in ['.xls', '.xlsx']:
            return 'XLS'
        elif file_ext in ['.mp4', '.avi', '.mov', '.wmv']:
            return 'VIDEO'
        elif file_ext in ['.mp3', '.wav']:
            return 'AUDIO'
        elif file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
            return 'IMAGE'
        elif file_ext in ['.zip', '.rar']:
            return 'ARCHIVE'
        elif file_ext in ['.txt', '.md']:
            return 'TXT'
        elif file_ext in ['.py', '.js', '.html', '.css', '.java', '.cpp']:
            return 'CODE'
        
        # Try to determine from content type if extension doesn't help
        if content_type:
            if 'pdf' in content_type.lower():
                return 'PDF'
            elif 'powerpoint' in content_type.lower() or 'presentation' in content_type.lower():
                return 'PPT'
            elif 'word' in content_type.lower() or 'document' in content_type.lower():
                return 'DOC'
            elif 'excel' in content_type.lower() or 'spreadsheet' in content_type.lower():
                return 'XLS'
            elif 'video' in content_type.lower():
                return 'VIDEO'
            elif 'audio' in content_type.lower():
                return 'AUDIO'
            elif 'image' in content_type.lower():
                return 'IMAGE'
            elif 'text' in content_type.lower():
                return 'TXT'
        
        return 'OTHER'
    except Exception as e:
        logger.warning(f"Could not determine file type from URL {url}: {str(e)}")
        return 'OTHER'

async def download_file_from_url(url: str, filename: str) -> tuple[str, int, str]:
    """Download file from URL and return local path, size, and content type"""
    try:
        logger.info(f"Starting download from URL: {url}")
        
        # Validate URL
        if not url.startswith(('http://', 'https://')):
            raise ValueError("Invalid URL: must start with http:// or https://")
        
        # Use aiohttp for async download
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise ValueError(f"Failed to download file: HTTP {response.status}")
                
                content_type = response.headers.get('content-type', '')
                content_length = response.headers.get('content-length')
                
                logger.info(f"Response: {response.status}, Content-Type: {content_type}, Content-Length: {content_length}")
                
                # Create local file path
                local_path = UPLOAD_BASE_DIR / "resources" / filename
                
                # Download file
                file_size = 0
                async with aiofiles.open(local_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
                        file_size += len(chunk)
                
                logger.info(f"File downloaded successfully: {local_path}, Size: {file_size} bytes")
                return str(local_path), file_size, content_type
                
    except Exception as e:
        logger.error(f"Error downloading file from {url}: {str(e)}")
        raise ValueError(f"Failed to download file: {str(e)}")

@router.post("/file-link")
async def create_file_link_resource(
    session_id: int = Form(...),
    title: str = Form(...),
    file_url: str = Form(...),
    description: str = Form(""),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Create a resource by downloading a file from a URL"""
    try:
        logger.info(f"Creating file-link resource: session_id={session_id}, title={title}, url={file_url}")
        
        # Validate session exists
        is_cohort = False
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        
        if not session:
            # Check for cohort session
            try:
                from cohort_specific_models import CohortCourseSession, CohortSessionContent
                session = db.query(CohortCourseSession).filter(CohortCourseSession.id == session_id).first()
                if session:
                    is_cohort = True
                else:
                    raise HTTPException(status_code=404, detail="Session not found")
            except ImportError:
                 raise HTTPException(status_code=404, detail="Session not found in regular or cohort courses")
            except HTTPException:
                 raise
        
        # Validate inputs
        if not title.strip():
            raise HTTPException(status_code=400, detail="Title is required")
        
        if not file_url.strip():
            raise HTTPException(status_code=400, detail="File URL is required")
        
        # Clean and validate URL
        file_url = file_url.strip()
        if not file_url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="Invalid URL: must start with http:// or https://")
        
        # Generate unique filename
        unique_filename = f"{uuid.uuid4()}"
        
        resource_id = None
        resource_type = "FILE_LINK"
        
        if is_cohort:
            # Create cohort session content
            content = CohortSessionContent(
                session_id=session_id,
                content_type="RESOURCE",
                title=title.strip(),
                description=description.strip() if description else None,
                file_path=file_url,
                file_type="FILE_LINK",
                file_size=0,
                uploaded_by=current_user.id
            )
            db.add(content)
            db.commit()
            db.refresh(content)
            resource_id = content.id
        else:
            # Create regular resource
            resource = Resource(
                session_id=session_id,
                title=title.strip(),
                resource_type=resource_type,
                file_path=file_url,
                file_size=0,
                description=description.strip() if description else None,
                uploaded_by=current_user.id
            )
            db.add(resource)
            db.commit()
            db.refresh(resource)
            resource_id = resource.id
        
        # Schedule background download
        from routers.resource_router import process_file_download_background
        background_tasks.add_task(process_file_download_background, session_id, resource_id, file_url, is_cohort)
        
        logger.info(f"File-link resource created successfully: ID={resource_id}, Type={resource_type}, IsCohort={is_cohort}")
        
        # Log the action
        try:
            from main import log_admin_action, log_presenter_action
            from database import Admin, Presenter
            
            if db.query(Admin).filter(Admin.id == current_user.id).first():
                log_admin_action(
                    admin_id=current_user.id,
                    admin_username=current_user.username,
                    action_type="CREATE",
                    resource_type="RESOURCE",
                    resource_id=resource_id,
                    details=f"Downloaded and created resource from URL: {title}"
                )
            elif db.query(Presenter).filter(Presenter.id == current_user.id).first():
                log_presenter_action(
                    presenter_id=current_user.id,
                    presenter_username=current_user.username,
                    action_type="CREATE",
                    resource_type="RESOURCE",
                    resource_id=resource_id,
                    details=f"Downloaded and created resource from URL: {title}"
                )
        except Exception as log_error:
            logger.warning(f"Failed to log action: {str(log_error)}")
        
        return {
            "message": "File link created successfully. Download initiated.",
            "resource_id": resource_id,
            "filename": unique_filename,
            "resource_type": resource_type
        }        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating file-link resource: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create resource from file link")

@router.get("/debug/{session_id}")
async def debug_session_resources(
    session_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Debug endpoint to check resources for a session"""
    try:
        resources = db.query(Resource).filter(Resource.session_id == session_id).all()
        
        result = []
        for r in resources:
            # Check if file exists
            file_exists = os.path.exists(r.file_path) if r.file_path else False
            
            result.append({
                "id": r.id,
                "session_id": r.session_id,
                "title": r.title,
                "resource_type": r.resource_type,
                "file_path": r.file_path,
                "file_size": r.file_size,
                "description": r.description,
                "file_exists": file_exists,
                "uploaded_at": r.uploaded_at,
                "created_at": r.created_at
            })
        
        return {
            "session_id": session_id,
            "resource_count": len(result),
            "resources": result
        }
        
    except Exception as e:
        logger.error(f"Debug resources error: {str(e)}")
        return {"error": str(e)}