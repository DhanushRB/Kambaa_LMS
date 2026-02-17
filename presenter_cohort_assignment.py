# Admin endpoints for managing presenter-cohort assignments

from fastapi import HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from database import get_db, Presenter, Cohort, PresenterCohort, Admin
from auth import get_current_admin_or_presenter
from pydantic import BaseModel
from typing import List
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class PresenterCohortAssign(BaseModel):
    presenter_id: int
    cohort_ids: List[int]

class PresenterAssignRequest(BaseModel):
    presenter_id: int

@router.post("/admin/cohorts/{cohort_id}/presenter")
async def assign_presenter_to_cohort(
    cohort_id: int,
    request_data: PresenterAssignRequest,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Assign a presenter to a cohort"""
    try:
        presenter_id = request_data.presenter_id
        
        # Verify cohort exists
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Verify presenter exists
        presenter = db.query(Presenter).filter(Presenter.id == presenter_id).first()
        if not presenter:
            raise HTTPException(status_code=404, detail="Presenter not found")
        
        # Check if assignment already exists
        existing = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == presenter_id,
            PresenterCohort.cohort_id == cohort_id
        ).first()
        
        if existing:
            return {
                "message": f"Presenter {presenter.username} is already assigned to cohort {cohort.name}",
                "assignment_id": existing.id,
                "already_exists": True
            }
        
        # Create assignment
        assignment = PresenterCohort(
            presenter_id=presenter_id,
            cohort_id=cohort_id,
            assigned_by=current_admin.id
        )
        
        db.add(assignment)
        db.commit()
        
        return {
            "message": f"Presenter {presenter.username} assigned to cohort {cohort.name}",
            "assignment_id": assignment.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Assign presenter to cohort error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to assign presenter to cohort")

@router.delete("/admin/cohorts/{cohort_id}/presenter")
async def remove_presenter_from_cohort(
    cohort_id: int,
    presenter_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Remove presenter assignment from a cohort"""
    try:
        assignment = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == presenter_id,
            PresenterCohort.cohort_id == cohort_id
        ).first()
        
        if not assignment:
            raise HTTPException(status_code=404, detail="Presenter assignment not found")
        
        db.delete(assignment)
        db.commit()
        
        return {"message": "Presenter removed from cohort successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Remove presenter from cohort error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to remove presenter from cohort")

@router.post("/admin/presenters/{presenter_id}/cohorts")
async def assign_cohorts_to_presenter(
    presenter_id: int,
    cohort_data: PresenterCohortAssign,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Assign multiple cohorts to a presenter"""
    try:
        # Verify presenter exists
        presenter = db.query(Presenter).filter(Presenter.id == presenter_id).first()
        if not presenter:
            raise HTTPException(status_code=404, detail="Presenter not found")
        
        assigned_cohorts = []
        errors = []
        
        for cohort_id in cohort_data.cohort_ids:
            # Verify cohort exists
            cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
            if not cohort:
                errors.append(f"Cohort ID {cohort_id} not found")
                continue
            
            # Check if assignment already exists
            existing = db.query(PresenterCohort).filter(
                PresenterCohort.presenter_id == presenter_id,
                PresenterCohort.cohort_id == cohort_id
            ).first()
            
            if existing:
                errors.append(f"Presenter already assigned to cohort {cohort.name}")
                continue
            
            # Create assignment
            assignment = PresenterCohort(
                presenter_id=presenter_id,
                cohort_id=cohort_id,
                assigned_by=current_admin.id
            )
            
            db.add(assignment)
            assigned_cohorts.append(cohort.name)
        
        db.commit()
        
        return {
            "message": f"Assigned {len(assigned_cohorts)} cohorts to presenter {presenter.username}",
            "assigned_cohorts": assigned_cohorts,
            "errors": errors
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Assign cohorts to presenter error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to assign cohorts to presenter")

@router.get("/admin/presenters/{presenter_id}/cohorts")
async def get_presenter_cohorts(
    presenter_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get cohorts assigned to a specific presenter"""
    try:
        # Verify presenter exists
        presenter = db.query(Presenter).filter(Presenter.id == presenter_id).first()
        if not presenter:
            raise HTTPException(status_code=404, detail="Presenter not found")
        
        # Get assigned cohorts
        assignments = db.query(PresenterCohort).filter(
            PresenterCohort.presenter_id == presenter_id
        ).all()
        
        cohorts = []
        for assignment in assignments:
            cohort = assignment.cohort
            cohorts.append({
                "id": cohort.id,
                "name": cohort.name,
                "description": cohort.description,
                "start_date": cohort.start_date,
                "end_date": cohort.end_date,
                "assigned_at": assignment.assigned_at
            })
        
        return {
            "presenter": {
                "id": presenter.id,
                "username": presenter.username,
                "email": presenter.email
            },
            "cohorts": cohorts
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get presenter cohorts error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch presenter cohorts")

@router.get("/admin/cohorts/{cohort_id}/presenters")
async def get_cohort_presenters(
    cohort_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get presenters assigned to a specific cohort"""
    try:
        # Verify cohort exists
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Get assigned presenters
        assignments = db.query(PresenterCohort).filter(
            PresenterCohort.cohort_id == cohort_id
        ).all()
        
        presenters = []
        for assignment in assignments:
            presenter = assignment.presenter
            presenters.append({
                "id": presenter.id,
                "username": presenter.username,
                "email": presenter.email,
                "assigned_at": assignment.assigned_at
            })
        
        return {
            "cohort": {
                "id": cohort.id,
                "name": cohort.name,
                "description": cohort.description
            },
            "presenters": presenters
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get cohort presenters error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch cohort presenters")