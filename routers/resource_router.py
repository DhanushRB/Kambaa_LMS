from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import get_db, Session as SessionModel, Resource, Module, Course
from auth import get_current_admin_or_presenter, get_current_presenter
from typing import Optional, Any
import logging
import os
from pathlib import Path
import uuid

router = APIRouter(prefix="/admin", tags=["Resource Management"])
logger = logging.getLogger(__name__)

# Upload directories
UPLOAD_BASE_DIR = Path("uploads")
UPLOAD_BASE_DIR.mkdir(exist_ok=True)
(UPLOAD_BASE_DIR / "resources").mkdir(exist_ok=True)
(UPLOAD_BASE_DIR / "course_banners").mkdir(exist_ok=True)

@router.post("/upload/resource")
async def upload_resource_simple(
    session_id: int = Form(...),
    file: UploadFile = File(...),
    title: str = Form(...),
    resource_type: str = Form("FILE"),
    description: Optional[str] = Form(None),
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Upload a resource file (simple endpoint)"""
    try:
        # Check if it's a cohort session first
        from cohort_specific_models import CohortCourseSession, CohortSessionContent
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
            
            return {
                "message": "Resource uploaded successfully",
                "resource_id": session_content.id,
                "filename": unique_filename
            }
        
        # Regular session handling
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Generate unique filename
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = UPLOAD_BASE_DIR / "resources" / unique_filename
        
        # Save file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Create resource record
        resource = Resource(
            session_id=session_id,
            title=title,
            resource_type=resource_type,
            file_path=str(file_path),
            file_size=len(content),
            description=description
        )
        
        db.add(resource)
        db.commit()
        db.refresh(resource)
        
        return {
            "message": "Resource uploaded successfully",
            "resource_id": resource.id,
            "filename": unique_filename
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Upload resource error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload resource")

@router.post("/sessions/{session_id}/resources")
async def upload_resource(
    session_id: int,
    file: UploadFile = File(...),
    title: str = Form(...),
    resource_type: str = Form(...),
    description: Optional[str] = Form(None),
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Upload a resource file for a session"""
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Generate unique filename
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = UPLOAD_BASE_DIR / "resources" / unique_filename
        
        # Save file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Create resource record
        resource = Resource(
            session_id=session_id,
            title=title,
            resource_type=resource_type,
            file_path=str(file_path),
            file_size=len(content),
            description=description
        )
        
        db.add(resource)
        db.commit()
        db.refresh(resource)
        
        return {
            "message": "Resource uploaded successfully",
            "resource_id": resource.id,
            "filename": unique_filename
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Upload resource error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload resource")

@router.post("/upload/course-banner")
async def upload_course_banner(
    file: UploadFile = File(...),
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Upload a course banner image with automatic resizing to 1280x420"""
    try:
        # Check roles - only Admin and Manager allowed
        from database import Admin, Manager
        is_admin = db.query(Admin).filter(Admin.id == current_user.id).first() is not None
        is_manager = db.query(Manager).filter(Manager.id == current_user.id).first() is not None
        
        if not (is_admin or is_manager):
            raise HTTPException(status_code=403, detail="Only Admins or Managers can upload banners")

        # Generate unique filename
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            raise HTTPException(status_code=400, detail="Invalid file type. Only JPG, PNG, WEBP are allowed.")
            
        unique_filename = f"banner_{uuid.uuid4()}.jpg" # Standardize to JPG for efficiency
        file_path = UPLOAD_BASE_DIR / "course_banners" / unique_filename
        
        # Read and process image
        from PIL import Image
        import io
        
        content = await file.read()
        image = Image.open(io.BytesIO(content))
        
        # Convert to RGB if necessary (handles PNG transparency)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
            
        # Target size
        target_width = 1280
        target_height = 420
        
        # Calculate aspect ratios
        img_width, img_height = image.size
        aspect = img_width / img_height
        target_aspect = target_width / target_height
        
        if aspect > target_aspect:
            # Image is wider than target - resize by height and crop width
            new_height = target_height
            new_width = int(new_height * aspect)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            left = (new_width - target_width) / 2
            image = image.crop((left, 0, left + target_width, target_height))
        else:
            # Image is taller than target - resize by width and crop height
            new_width = target_width
            new_height = int(new_width / aspect)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            top = (new_height - target_height) / 2
            image = image.crop((0, top, target_width, top + target_height))
            
        # Save processed image
        image.save(file_path, "JPEG", quality=85, optimize=True)
        
        banner_url = f"/api/course-banners/{unique_filename}"
        
        return {
            "message": "Banner uploaded and resized successfully",
            "banner_url": banner_url,
            "filename": unique_filename
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload banner error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process and upload banner image")

@router.get("/resources")
async def get_resources(
    session_id: Optional[int] = None,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get resources, optionally filtered by session_id"""
    try:
        query = db.query(Resource)
        
        if session_id:
            query = query.filter(Resource.session_id == session_id)
        
        resources = query.all()
        
        result = []
        for resource in resources:
            filename = os.path.basename(resource.file_path) if resource.file_path else None
            
            result.append({
                "id": resource.id,
                "session_id": resource.session_id,
                "title": resource.title,
                "resource_type": resource.resource_type,
                "filename": filename,
                "file_size": resource.file_size,
                "description": resource.description,
                "download_url": f"/api/resources/{filename}" if filename else None,
                "uploaded_at": resource.uploaded_at
            })
        
        return {"resources": result}
    except Exception as e:
        logger.error(f"Get resources error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch resources")

@router.get("/sessions/{session_id}/resources")
async def get_session_resources(
    session_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get all resources for a session"""
    try:
        resources = db.query(Resource).filter(Resource.session_id == session_id).all()
        
        result = []
        for resource in resources:
            filename = os.path.basename(resource.file_path) if resource.file_path else None
            
            result.append({
                "id": resource.id,
                "title": resource.title,
                "resource_type": resource.resource_type,
                "filename": filename,
                "file_size": resource.file_size,
                "description": resource.description,
                "download_url": f"/api/resources/{filename}" if filename else None,
                "uploaded_at": resource.uploaded_at
            })
        
        return {"resources": result}
    except Exception as e:
        logger.error(f"Get session resources error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch resources")

@router.put("/resources/{resource_id}")
async def update_resource(
    resource_id: Any,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    resource_type: Optional[str] = Form(None),
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Update resource metadata"""
    try:
        # Handle prefixed IDs
        if isinstance(resource_id, str):
            if "_" in resource_id:
                try:
                    resource_id = int(resource_id.split("_")[1])
                except (IndexError, ValueError):
                    pass
            elif resource_id.isdigit():
                resource_id = int(resource_id)

        resource = db.query(Resource).filter(Resource.id == resource_id).first()
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        if title is not None:
            resource.title = title
        if description is not None:
            resource.description = description
        if resource_type is not None:
            resource.resource_type = resource_type
        
        db.commit()
        
        return {"message": "Resource updated successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Update resource error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update resource")

@router.delete("/resources/{resource_id}")
async def delete_resource(
    resource_id: Any,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Delete a resource"""
    try:
        # Handle prefixed IDs
        if isinstance(resource_id, str):
            if "_" in resource_id:
                try:
                    resource_id = int(resource_id.split("_")[1])
                except (IndexError, ValueError):
                    pass
            elif resource_id.isdigit():
                resource_id = int(resource_id)
                
        resource = db.query(Resource).filter(Resource.id == resource_id).first()
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        # Delete file from filesystem
        if resource.file_path and os.path.exists(resource.file_path):
            os.remove(resource.file_path)
        
        # Delete database record
        db.delete(resource)
        db.commit()
        
        return {"message": "Resource deleted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Delete resource error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete resource")

@router.get("/resources/{resource_id}/download")
async def download_resource(
    resource_id: Any,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Download a resource file"""
    try:
        # Handle prefixed IDs
        if isinstance(resource_id, str):
            if "_" in resource_id:
                try:
                    resource_id = int(resource_id.split("_")[1])
                except (IndexError, ValueError):
                    pass
            elif resource_id.isdigit():
                resource_id = int(resource_id)

        resource = db.query(Resource).filter(Resource.id == resource_id).first()
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        if not resource.file_path or not os.path.exists(resource.file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        filename = os.path.basename(resource.file_path)
        return FileResponse(
            resource.file_path,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
        )
    except Exception as e:
        logger.error(f"Download resource error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download resource")

@router.get("/resources/{resource_id}/view")
async def view_resource(
    resource_id: Any,
    db: Session = Depends(get_db)
):
    """View a resource file by ID - accessible to all authenticated users"""
    try:
        # Handle prefixed IDs
        if isinstance(resource_id, str):
            if "_" in resource_id:
                try:
                    resource_id = int(resource_id.split("_")[1])
                except (IndexError, ValueError):
                    pass
            elif resource_id.isdigit():
                resource_id = int(resource_id)

        logger.info(f"Attempting to view resource {resource_id}")
        
        # First check regular resources table
        resource = db.query(Resource).filter(Resource.id == resource_id).first()
        
        if not resource:
            # Check cohort session content table
            try:
                from cohort_specific_models import CohortSessionContent
                cohort_resource = db.query(CohortSessionContent).filter(
                    CohortSessionContent.id == resource_id,
                    CohortSessionContent.content_type == "RESOURCE"
                ).first()
                
                if cohort_resource:
                    logger.info(f"Found cohort resource {resource_id}: {cohort_resource.file_path}")
                    if not cohort_resource.file_path or not os.path.exists(cohort_resource.file_path):
                        logger.error(f"Cohort resource file not found: {cohort_resource.file_path}")
                        raise HTTPException(status_code=404, detail="File not found")
                    
                    filename = os.path.basename(cohort_resource.file_path)
                    file_ext = os.path.splitext(filename)[1].lower()
                    
                    # Determine media type
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
                    elif file_ext in [".doc", ".docx"]:
                        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    else:
                        media_type = "application/octet-stream"
                    
                    return FileResponse(cohort_resource.file_path, media_type=media_type)
            except ImportError:
                logger.warning("CohortSessionContent model not available")
            
            logger.error(f"Resource {resource_id} not found in any table")
            raise HTTPException(status_code=404, detail="Resource not found")
        
        logger.info(f"Found regular resource {resource_id}: {resource.file_path}")
        
        if not resource.file_path or not os.path.exists(resource.file_path):
            logger.error(f"Resource file not found: {resource.file_path}")
            raise HTTPException(status_code=404, detail="File not found")
        
        filename = os.path.basename(resource.file_path)
        file_ext = os.path.splitext(filename)[1].lower()
        
        # Determine media type
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
        elif file_ext in [".doc", ".docx"]:
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            media_type = "application/octet-stream"
        
        return FileResponse(resource.file_path, media_type=media_type)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"View resource error for resource {resource_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to view resource: {str(e)}")

from fastapi import BackgroundTasks
from link_downloader_service import download_file

async def process_file_download_background(session_id: int, resource_id: int, file_url: str, is_cohort: bool = False):
    """Background task to download and update resource"""
    # Create new session scope for background task
    from database import SessionLocal
    db = SessionLocal()
    try:
        logger.info(f"Starting download for resource {resource_id} from {file_url} (Cohort: {is_cohort})")
        
        # Download logic
        file_path, filename, mime_type, size = download_file(file_url, UPLOAD_BASE_DIR / "resources")
        
        # Determine resource type from mime type
        resource_type = "FILE"
        if "video" in mime_type:
            resource_type = "VIDEO"
        elif "pdf" in mime_type:
            resource_type = "PDF"
        elif "image" in mime_type:
            resource_type = "IMAGE"
        elif "text" in mime_type:
            resource_type = "TEXT"
        elif "presentation" in mime_type:
            resource_type = "PPT"
        elif "document" in mime_type:
            resource_type = "DOC"
            
        logger.info(f"Download complete: {file_path}, type={resource_type}, size={size}")
        
        if is_cohort:
            from cohort_specific_models import CohortSessionContent
            resource = db.query(CohortSessionContent).filter(CohortSessionContent.id == resource_id).first()
            if resource:
                resource.file_path = str(file_path)
                resource.file_size = size
                resource.file_type = resource_type
                # Update description to indicate local copy (REMOVED: " (Local Copy)")
                resource.description = (resource.description or "")
                db.commit()
                logger.info(f"Updated cohort resource {resource_id} with local file info")
        else:
            # Regular resource update
            resource = db.query(Resource).filter(Resource.id == resource_id).first()
            if resource:
                resource.file_path = str(file_path)
                resource.file_size = size
                resource.resource_type = resource_type
                resource.description = (resource.description or "")
                db.commit()
                logger.info(f"Updated resource {resource_id} with local file info")
            
    except Exception as e:
        logger.error(f"Failed to download/update resource {resource_id}: {str(e)}")
        # Optionally update resource description with error
        if is_cohort:
            from cohort_specific_models import CohortSessionContent
            resource = db.query(CohortSessionContent).filter(CohortSessionContent.id == resource_id).first()
        else:
            resource = db.query(Resource).filter(Resource.id == resource_id).first()
            
        if resource:
            resource.description = (resource.description or "") + f" [Download Failed: {str(e)}]"
            db.commit()
    finally:
        db.close()

@router.post("/sessions/{session_id}/file-links")
async def create_file_link(
    session_id: int,
    title: str = Form(...),
    file_url: str = Form(...),
    description: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Create a file link resource (external URL). Automatically attempts to download file if clear URL."""
    try:
        # Check if it's a cohort session first
        from cohort_specific_models import CohortCourseSession, CohortSessionContent
        cohort_session = db.query(CohortCourseSession).filter(CohortCourseSession.id == session_id).first()
        
        if cohort_session:
             # Create cohort session content for the link
            resource = CohortSessionContent(
                session_id=session_id,
                content_type="RESOURCE",
                title=title,
                description=description,
                file_path=file_url, # Store URL initially
                file_type="FILE_LINK",
                file_size=0,
                uploaded_by=None
            )
            
            db.add(resource)
            db.commit()
            db.refresh(resource)
             
            # Schedule background download
            background_tasks.add_task(process_file_download_background, session_id, resource.id, file_url, is_cohort=True)
            
            return {
                "message": "File link created successfully (Cohort). Download initiated.",
                "resource_id": resource.id
            }

        # Regular session handling
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        resource_type = "FILE_LINK"
        
        # Create resource initially as a link
        resource = Resource(
            session_id=session_id,
            title=title,
            resource_type=resource_type,
            file_path=file_url,  # Store URL in file_path for FILE_LINK type initially
            file_size=0,
            description=description
        )
        
        db.add(resource)
        db.commit()
        db.refresh(resource)
        
        # Schedule background download
        background_tasks.add_task(process_file_download_background, session_id, resource.id, file_url, is_cohort=False)
        
        return {
            "message": "File link created successfully. Download initiated.",
            "resource_id": resource.id
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Create file link error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create file link")

@router.get("/resources/stats")
async def get_resource_stats(
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get resource statistics"""
    try:
        total_resources = db.query(Resource).count()
        
        # Count by type
        resource_types = db.query(Resource.resource_type, db.func.count(Resource.id)).group_by(Resource.resource_type).all()
        type_counts = {rtype: count for rtype, count in resource_types}
        
        # Calculate total file size
        total_size = db.query(db.func.sum(Resource.file_size)).scalar() or 0
        
        return {
            "total_resources": total_resources,
            "resource_types": type_counts,
            "total_file_size_bytes": total_size,
            "total_file_size_mb": round(total_size / (1024 * 1024), 2)
        }
    except Exception as e:
        logger.error(f"Get resource stats error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch resource statistics")

@router.get("/resources/{resource_id}/debug")
async def debug_resource(
    resource_id: Any,
    db: Session = Depends(get_db)
):
    """Debug endpoint to check resource existence"""
    try:
        # Handle prefixed IDs
        if isinstance(resource_id, str):
            if "_" in resource_id:
                try:
                    resource_id = int(resource_id.split("_")[1])
                except (IndexError, ValueError):
                    pass
            elif resource_id.isdigit():
                resource_id = int(resource_id)

        # Check regular resources
        resource = db.query(Resource).filter(Resource.id == resource_id).first()
        
        # Check cohort session content
        cohort_resource = None
        try:
            from cohort_specific_models import CohortSessionContent
            cohort_resource = db.query(CohortSessionContent).filter(
                CohortSessionContent.id == resource_id
            ).first()
        except ImportError:
            pass
        
        return {
            "resource_id": resource_id,
            "regular_resource": {
                "exists": resource is not None,
                "file_path": resource.file_path if resource else None,
                "file_exists": os.path.exists(resource.file_path) if resource and resource.file_path else False
            },
            "cohort_resource": {
                "exists": cohort_resource is not None,
                "content_type": cohort_resource.content_type if cohort_resource else None,
                "file_path": cohort_resource.file_path if cohort_resource else None,
                "file_exists": os.path.exists(cohort_resource.file_path) if cohort_resource and cohort_resource.file_path else False
            }
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/debug/resources/{resource_id}")
async def debug_resource_legacy(
    resource_id: Any,
    db: Session = Depends(get_db)
):
    """Legacy debug endpoint to match frontend expectation"""
    return await debug_resource(resource_id, db)

async def bulk_upload_resources(
    session_id: int = Form(...),
    files: list[UploadFile] = File(...),
    resource_type: str = Form("FILE"),
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Upload multiple resources at once"""
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        uploaded_resources = []
        
        for file in files:
            try:
                # Generate unique filename
                file_ext = os.path.splitext(file.filename)[1]
                unique_filename = f"{uuid.uuid4()}{file_ext}"
                file_path = UPLOAD_BASE_DIR / "resources" / unique_filename
                
                # Save file
                content = await file.read()
                with open(file_path, "wb") as f:
                    f.write(content)
                
                # Create resource record
                resource = Resource(
                    session_id=session_id,
                    title=file.filename,
                    resource_type=resource_type,
                    file_path=str(file_path),
                    file_size=len(content),
                    description=f"Bulk uploaded file: {file.filename}"
                )
                
                db.add(resource)
                uploaded_resources.append({
                    "filename": file.filename,
                    "unique_filename": unique_filename,
                    "size": len(content)
                })
                
            except Exception as file_error:
                logger.error(f"Failed to upload {file.filename}: {str(file_error)}")
                continue
        
        db.commit()
        
        return {
            "message": f"Successfully uploaded {len(uploaded_resources)} resources",
            "uploaded_files": uploaded_resources
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Bulk upload resources error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to bulk upload resources")