from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pathlib import Path
import os
import uuid

from database import get_db, Admin, User, Course, Cohort
from auth import get_current_admin_or_presenter, get_current_user, get_current_user_any_role
from badge_models import BadgeConfiguration, AwardedBadge, BadgeAuditLog
from cohort_specific_models import CohortSpecificCourse
from badge_service import BadgeService
from schemas import BadgeConfigCreate, BadgeConfigUpdate, BadgeConfigResponse, AwardedBadgeResponse

router = APIRouter(prefix="/api/v1/badges", tags=["Badges"])

UPLOAD_DIR = Path("uploads/badge_icons")

@router.post("/upload-icon")
async def upload_badge_icon(
    file: UploadFile = File(...),
    current_user = Depends(get_current_admin_or_presenter)
):
    """
    Uploads a badge icon image (Admin only).
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
        
    ext = os.path.splitext(file.filename)[1].lower()
    if not ext:
        ext = ".png" # Default
        
    filename = f"{uuid.uuid4()}{ext}"
    file_path = UPLOAD_DIR / filename
    
    # Ensure the upload directory exists
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
            
        # Return the public URL
        return {"url": f"/api/badge-icons/{filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload icon: {str(e)}")

@router.post("/configure", response_model=BadgeConfigResponse)
def create_badge_config(
    config: BadgeConfigCreate, 
    db: Session = Depends(get_db), 
    current_user = Depends(get_current_admin_or_presenter)
):
    """
    Creates a new badge configuration (Admin only).
    """
    # Filter out fields that are not in the model
    model_data = {k: v for k, v in config.dict().items() if hasattr(BadgeConfiguration, k)}
    
    db_config = BadgeConfiguration(
        **model_data,
        created_by=current_user.id
    )
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config

@router.get("/configurations", response_model=List[BadgeConfigResponse])
def get_badge_configurations(
    db: Session = Depends(get_db), 
    current_user = Depends(get_current_admin_or_presenter)
):
    """
    Lists all badge configurations with enriched metadata (Admin only).
    """
    configs = db.query(BadgeConfiguration).all()
    results = []
    
    
    for config in configs:
        # Convert to Pydantic model
        res = BadgeConfigResponse.from_orm(config)
        
        # Enrich with cohort name
        if config.cohort_id:
            cohort = db.query(Cohort).filter(Cohort.id == config.cohort_id).first()
            if cohort:
                res.cohort_name = cohort.name
                
        # Enrich with course title
        if config.cohort_specific_course_id:
            course = db.query(CohortSpecificCourse).filter(CohortSpecificCourse.id == config.cohort_specific_course_id).first()
            if course:
                res.course_title = course.title
                res.is_cohort_specific = True
        elif config.course_id:
            course = db.query(Course).filter(Course.id == config.course_id).first()
            if course:
                res.course_title = course.title
                res.is_cohort_specific = False
                
        results.append(res)
        
    return results

@router.put("/{config_id}", response_model=BadgeConfigResponse)
def update_badge_config(
    config_id: int,
    config_update: BadgeConfigUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_or_presenter)
):
    """
    Updates an existing badge configuration (Admin only).
    """
    db_config = db.query(BadgeConfiguration).filter(BadgeConfiguration.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Configuration not found")
        
    update_data = config_update.dict(exclude_unset=True)
    
    # Filter out fields that are not in the model
    model_data = {k: v for k, v in update_data.items() if hasattr(BadgeConfiguration, k)}
    
    for key, value in model_data.items():
        setattr(db_config, key, value)
        
    db.commit()
    db.refresh(db_config)
    return db_config

from fastapi.responses import StreamingResponse
import csv
import io

@router.get("/preview/{config_id}")
def preview_eligible_users(
    config_id: int, 
    db: Session = Depends(get_db), 
    current_user = Depends(get_current_admin_or_presenter)
):
    """
    Runs the rules and returns students eligible for a badge (Admin only).
    Does not issue badges yet.
    """
    results = BadgeService.process_badge_evaluation(db, config_id)
    if "error" in results:
        raise HTTPException(status_code=404, detail=results["error"])
    return results

@router.get("/export-evaluation/{config_id}")
def export_badge_evaluation(
    config_id: int,
    status: str = "eligible",  # "eligible" or "rejected"
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_or_presenter)
):
    """
    Exports evaluation results (eligible or rejected) for a badge configuration to CSV (Admin only).
    """
    results = BadgeService.process_badge_evaluation(db, config_id)
    if "error" in results:
        raise HTTPException(status_code=404, detail=results["error"])
        
    evaluations = results.get("evaluations", [])
    
    # Map status to target list
    target_key = "eligible_now"
    if status.lower() == "issued":
        target_key = "already_issued"
    elif status.lower() == "rejected":
        target_key = "rejected"
        
    data_to_export = results.get(target_key, [])
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    if target_key in ["eligible_now", "already_issued"]:
        # Header for Success categories
        writer.writerow(["Student Name", "Email", "Attendance %", "Assignments Completed"])
        # Data
        for item in data_to_export:
            writer.writerow([
                item.get("name") or item.get("username"),
                item.get("email"),
                f"{item.get('attendance_percentage', 0):.1f}%",
                f"{item.get('submitted_count', 0)} / {item.get('total_assignments', 0)}"
            ])
    else:
        # Header for Rejected
        writer.writerow(["Student Name", "Email", "Status"])
        # Data
        for item in data_to_export:
            writer.writerow([
                item.get("name") or item.get("username"),
                item.get("email"),
                "Pending"
            ])
    
    output.seek(0)
    
    # Return streaming response
    filename = f"{status}_students_badge_{config_id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
 
@router.post("/issue/{config_id}")
def issue_badges(
    config_id: int, 
    user_ids: List[int],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user = Depends(get_current_admin_or_presenter)
):
    """
    Confirms and issues badges to selected students (Admin only).
    Triggers automated emails.
    """
    # Background task to send emails can be optimized here if needed
    # but currently service handles it directly
    results = BadgeService.issue_badges(db, config_id, user_ids)
    if "error" in results:
        raise HTTPException(status_code=404, detail=results["error"])
    return results

@router.get("/my-badges", response_model=List[AwardedBadgeResponse])
def get_user_badges(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Returns badges earned by the logged-in student.
    """
    badges = db.query(AwardedBadge).filter(AwardedBadge.user_id == current_user.id).all()
    
    # Enrichment
    results = []
    for badge in badges:
        res = AwardedBadgeResponse.from_orm(badge)
        res.badge_title = badge.configuration.title
        res.badge_icon = badge.configuration.icon_url
        results.append(res)
        
    return results

@router.get("/available")
def get_available_badges(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Returns badges the student hasn't earned yet, along with eligibility details.
    """
    return BadgeService.get_available_badges_for_student(db, current_user.id)

@router.get("/audit-logs/{config_id}")
def get_badge_audit_logs(
    config_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_or_presenter)
):
    """
    Returns evaluation history for a specific badge (Admin only).
    """
    logs = db.query(BadgeAuditLog).filter(BadgeAuditLog.badge_config_id == config_id).all()
    return logs

@router.delete("/{config_id}")
def delete_badge_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_or_presenter)
):
    """
    Deletes a badge configuration and its associated audit logs (Admin only).
    """
    config = db.query(BadgeConfiguration).filter(BadgeConfiguration.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    # Delete the config (SQLAlchemy handles cascades automatically)
    db.delete(config)
    db.commit()
    
    return {"message": "Badge configuration deleted successfully"}
