from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from datetime import timedelta
from database import get_db, User, Admin, Presenter, Manager
from auth import verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from schemas import AdminLogin
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])

class UserLogin(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    role: str = Field(..., pattern="^(Student)$")

# Import logging functions
from main import log_admin_action, log_presenter_action, log_student_action

@router.post("/login")
async def login(user_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    try:
        if user_data.role != "Student":
            raise HTTPException(status_code=400, detail="Invalid role for user login")
        
        user = db.query(User).filter(
            User.username == user_data.username, 
            User.role == user_data.role
        ).first()
        
        if not user or not verify_password(user_data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "role": user.role, "user_id": user.id}, 
            expires_delta=access_token_expires
        )
        
        log_student_action(
            student_id=user.id,
            student_username=user.username,
            action_type="LOGIN",
            resource_type="STUDENT_SESSION",
            details=f"Student login successful: {user.username}",
            ip_address=request.client.host if request.client else "127.0.0.1"
        )
        
        return {
            "access_token": access_token, 
            "token_type": "bearer", 
            "role": user.role, 
            "user_id": user.id,
            "username": user.username,
            "email": user.email
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/admin/login")
async def admin_login(admin_data: AdminLogin, request: Request, db: Session = Depends(get_db)):
    try:
        admin = db.query(Admin).filter(
            Admin.username == admin_data.username
        ).first()
        
        if not admin or not verify_password(admin_data.password, admin.password_hash):
            raise HTTPException(status_code=401, detail="Invalid admin credentials")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": admin.username, "role": "Admin", "user_id": admin.id}, 
            expires_delta=access_token_expires
        )
        
        log_admin_action(
            admin_id=admin.id,
            admin_username=admin.username,
            action_type="LOGIN",
            resource_type="ADMIN_SESSION",
            details=f"Admin login successful: {admin.username}",
            ip_address=request.client.host if request.client else "127.0.0.1"
        )
        
        return {
            "access_token": access_token, 
            "token_type": "bearer", 
            "role": "Admin", 
            "user_id": admin.id,
            "username": admin.username,
            "email": admin.email
        }
    except Exception as e:
        logger.error(f"Admin login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/presenter/login")
async def presenter_login(presenter_data: AdminLogin, request: Request, db: Session = Depends(get_db)):
    try:
        presenter = db.query(Presenter).filter(
            Presenter.username == presenter_data.username
        ).first()
        
        if not presenter or not verify_password(presenter_data.password, presenter.password_hash):
            raise HTTPException(status_code=401, detail="Invalid presenter credentials")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": presenter.username, "role": "Presenter", "user_id": presenter.id}, 
            expires_delta=access_token_expires
        )
        
        log_presenter_action(
            presenter_id=presenter.id,
            presenter_username=presenter.username,
            action_type="LOGIN",
            resource_type="PRESENTER_SESSION",
            details=f"Presenter login successful: {presenter.username}",
            ip_address=request.client.host if request.client else "127.0.0.1"
        )
        
        return {
            "access_token": access_token, 
            "token_type": "bearer", 
            "role": "Presenter", 
            "user_id": presenter.id,
            "username": presenter.username,
            "email": presenter.email
        }
    except Exception as e:
        logger.error(f"Presenter login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/manager/login")
async def manager_login(manager_data: AdminLogin, request: Request, db: Session = Depends(get_db)):
    try:
        manager = db.query(Manager).filter(
            Manager.username == manager_data.username
        ).first()
        
        if not manager or not verify_password(manager_data.password, manager.password_hash):
            raise HTTPException(status_code=401, detail="Invalid manager credentials")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": manager.username, "role": "Manager", "user_id": manager.id}, 
            expires_delta=access_token_expires
        )
        
        log_admin_action(
            admin_id=manager.id,
            admin_username=manager.username,
            action_type="LOGIN",
            resource_type="MANAGER_SESSION",
            details=f"Manager login successful: {manager.username}",
            ip_address=request.client.host if request.client else "127.0.0.1"
        )
        
        return {
            "access_token": access_token, 
            "token_type": "bearer", 
            "role": "Manager", 
            "user_id": manager.id,
            "username": manager.username,
            "email": manager.email
        }
    except Exception as e:
        logger.error(f"Manager login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")