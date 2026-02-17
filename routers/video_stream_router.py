from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from database import get_db, Resource
from auth import get_current_user_any_role, SECRET_KEY, ALGORITHM
from jose import jwt, JWTError
from datetime import datetime, timedelta
import os
import logging

router = APIRouter(prefix="/api/video", tags=["Secure Video Streaming"])
logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024 
VIDEO_TOKEN_EXPIRY_SECONDS = 300 
VIDEO_TOKEN_SECRET = SECRET_KEY + "_video_secure"

def create_video_token(resource_id: int, user_id: int, role: str, source: str) -> str:
    expire = datetime.utcnow() + timedelta(seconds=VIDEO_TOKEN_EXPIRY_SECONDS)
    to_encode = {
        "sub": str(user_id),
        "role": role,
        "resource_id": resource_id,
        "source": source,
        "type": "video_stream",
        "exp": expire
    }
    return jwt.encode(to_encode, VIDEO_TOKEN_SECRET, algorithm=ALGORITHM)

def verify_video_token(token: str, resource_id: int):
    try:
        payload = jwt.decode(token, VIDEO_TOKEN_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "video_stream":
            raise HTTPException(status_code=401, detail="Invalid token type")
        if int(payload.get("resource_id")) != resource_id:
            raise HTTPException(status_code=403, detail="Token mismatch for this resource")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired video token")

@router.post("/{resource_id}/token")
async def get_video_stream_token(
    resource_id: int,
    source: str = "resource",
    current_user = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    resource = None
    if source == "cohort":
        try:
            from cohort_specific_models import CohortSessionContent
            resource = db.query(CohortSessionContent).filter(
                CohortSessionContent.id == resource_id,
                CohortSessionContent.content_type == "RESOURCE"
            ).first()
        except ImportError:
            pass
    else:
        resource = db.query(Resource).filter(Resource.id == resource_id).first()
    
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    if not resource.file_path or not os.path.exists(resource.file_path):
        raise HTTPException(status_code=404, detail="Video file not found")
        
    user_id = current_user.get("id")
    role = current_user.get("role")
    token = create_video_token(resource_id, user_id, role, source)
    
    return {"token": token, "resource_id": resource_id}

@router.get("/{resource_id}/stream")
async def stream_video(
    resource_id: int,
    token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    payload = verify_video_token(token, resource_id)
    source = payload.get("source", "resource")
    
    resource = None
    if source == "cohort":
        try:
            from cohort_specific_models import CohortSessionContent
            resource = db.query(CohortSessionContent).filter(
                CohortSessionContent.id == resource_id
            ).first()
        except ImportError:
            pass
    else:
        resource = db.query(Resource).filter(Resource.id == resource_id).first()
            
    if not resource or not resource.file_path:
        raise HTTPException(status_code=404, detail="Resource not found")
        
    file_path = resource.file_path
    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": "video/mp4",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }

    if range_header:
        try:
            start, end = range_header.replace("bytes=", "").split("-")
            start = int(start)
            end = int(end) if end else file_size - 1
            if start >= file_size:
                 return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})
            length = end - start + 1
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            headers["Content-Length"] = str(length)
            
            def iterfile():
                with open(file_path, "rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk_size = min(CHUNK_SIZE, remaining)
                        data = f.read(chunk_size)
                        if not data: break
                        yield data
                        remaining -= len(data)

            return StreamingResponse(iterfile(), status_code=206, headers=headers, media_type="video/mp4")
        except ValueError:
            pass

    headers["Content-Length"] = str(file_size)
    def iterfile_full():
        with open(file_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                yield chunk
                
    return StreamingResponse(iterfile_full(), headers=headers, media_type="video/mp4")
