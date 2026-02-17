from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, Admin, Presenter, Manager
from auth import get_current_admin
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/admin", tags=["Admin Members"])

class MemberUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None

@router.put("/admins/{admin_id}")
async def update_admin(
    admin_id: int,
    data: MemberUpdate,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    if data.username:
        admin.username = data.username
    if data.email:
        admin.email = data.email
    if data.password:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        admin.password_hash = pwd_context.hash(data.password)
    
    db.commit()
    return {"message": "Admin updated successfully"}

@router.delete("/admins/{admin_id}")
async def delete_admin(
    admin_id: int,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    db.delete(admin)
    db.commit()
    return {"message": "Admin deleted successfully"}

@router.put("/presenters/{presenter_id}")
async def update_presenter(
    presenter_id: int,
    data: MemberUpdate,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    presenter = db.query(Presenter).filter(Presenter.id == presenter_id).first()
    if not presenter:
        raise HTTPException(status_code=404, detail="Presenter not found")
    
    if data.username:
        presenter.username = data.username
    if data.email:
        presenter.email = data.email
    if data.password:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        presenter.password_hash = pwd_context.hash(data.password)
    
    db.commit()
    return {"message": "Presenter updated successfully"}

@router.delete("/presenters/{presenter_id}")
async def delete_presenter(
    presenter_id: int,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    presenter = db.query(Presenter).filter(Presenter.id == presenter_id).first()
    if not presenter:
        raise HTTPException(status_code=404, detail="Presenter not found")
    
    db.delete(presenter)
    db.commit()
    return {"message": "Presenter deleted successfully"}

@router.put("/managers/{manager_id}")
async def update_manager(
    manager_id: int,
    data: MemberUpdate,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    manager = db.query(Manager).filter(Manager.id == manager_id).first()
    if not manager:
        raise HTTPException(status_code=404, detail="Manager not found")
    
    if data.username:
        manager.username = data.username
    if data.email:
        manager.email = data.email
    if data.password:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        manager.password_hash = pwd_context.hash(data.password)
    
    db.commit()
    return {"message": "Manager updated successfully"}

@router.delete("/managers/{manager_id}")
async def delete_manager(
    manager_id: int,
    current_admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    manager = db.query(Manager).filter(Manager.id == manager_id).first()
    if not manager:
        raise HTTPException(status_code=404, detail="Manager not found")
    
    db.delete(manager)
    db.commit()
    return {"message": "Manager deleted successfully"}
