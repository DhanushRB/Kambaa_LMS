from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import timedelta
from pydantic import BaseModel, Field
from database import get_db, User, Admin, Presenter, Mentor, Manager
from jose import jwt, JWTError
from auth import verify_password, create_access_token_with_session, ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM
from session_manager import SessionManager
import logging

import logging
from logging_utils import log_admin_action, log_presenter_action, log_student_action, log_mentor_action

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic models for login requests
class LoginRequest(BaseModel):
    # For compatibility with existing frontend, we keep the field name 'username'
    # but treat it as the user's email for authentication.
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

# Login page endpoints for frontend
@router.get("/admin/login-page")
async def admin_login_page():
    return {"page": "admin_login", "title": "Admin Login", "role": "Admin"}

@router.get("/manager/login-page")
async def manager_login_page():
    return {"page": "manager_login", "title": "Manager Login", "role": "Manager"}

@router.get("/presenter/login-page")
async def presenter_login_page():
    return {"page": "presenter_login", "title": "Presenter Login", "role": "Presenter"}

@router.get("/mentor/login-page")
async def mentor_login_page():
    return {"page": "mentor_login", "title": "Mentor Login", "role": "Mentor"}

@router.get("/student/login-page")
async def student_login_page():
    return {"page": "student_login", "title": "Student/Faculty Login", "role": "Student"}

# Admin login endpoint
@router.post("/admin/login")
async def admin_login(login_data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    try:
        # Allow login with either username or email
        # Email-only login
        admin = db.query(Admin).filter(Admin.email == login_data.username).first()
        
        if not admin or not verify_password(login_data.password, admin.password_hash):
            raise HTTPException(status_code=401, detail="Invalid admin credentials")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token_with_session(
            data={"sub": admin.username, "role": "Admin", "user_id": admin.id}, 
            db=db,
            request=request,
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
            "email": admin.email,
            "dashboard_url": "/admin/dashboard",
            "login_url": "/auth/admin-login"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Manager login endpoint
@router.post("/manager/login")
async def manager_login(login_data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    try:
        # Allow login with either username or email
        # Email-only login
        manager = db.query(Manager).filter(Manager.email == login_data.username).first()
        
        if not manager or not verify_password(login_data.password, manager.password_hash):
            raise HTTPException(status_code=401, detail="Invalid manager credentials")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token_with_session(
            data={"sub": manager.username, "role": "Manager", "user_id": manager.id}, 
            db=db,
            request=request,
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
            "email": manager.email,
            "dashboard_url": "/manager/dashboard",
            "login_url": "/auth/manager-login"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manager login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Presenter login endpoint
@router.post("/presenter/login")
async def presenter_login(login_data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    try:
        # Allow login with either username or email
        # Email-only login
        presenter = db.query(Presenter).filter(Presenter.email == login_data.username).first()
        
        if not presenter or not verify_password(login_data.password, presenter.password_hash):
            raise HTTPException(status_code=401, detail="Invalid presenter credentials")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token_with_session(
            data={"sub": presenter.username, "role": "Presenter", "user_id": presenter.id}, 
            db=db,
            request=request,
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
            "email": presenter.email,
            "dashboard_url": "/presenter/dashboard",
            "login_url": "/auth/presenter-login"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Presenter login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Mentor login endpoint
@router.post("/mentor/login")
async def mentor_login(login_data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    try:
        # Allow login with either username or email
        # Email-only login
        mentor = db.query(Mentor).filter(Mentor.email == login_data.username).first()
        
        if not mentor or not verify_password(login_data.password, mentor.password_hash):
            raise HTTPException(status_code=401, detail="Invalid mentor credentials")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token_with_session(
            data={"sub": mentor.username, "role": "Mentor", "user_id": mentor.id}, 
            db=db,
            request=request,
            expires_delta=access_token_expires
        )
        
        log_mentor_action(
            mentor_id=mentor.id,
            mentor_username=mentor.username,
            action_type="LOGIN",
            resource_type="MENTOR_SESSION",
            details=f"Mentor login successful: {mentor.username}",
            ip_address=request.client.host if request.client else "127.0.0.1"
        )
        
        return {
            "access_token": access_token, 
            "token_type": "bearer", 
            "role": "Mentor", 
            "user_id": mentor.id,
            "username": mentor.username,
            "email": mentor.email,
            "dashboard_url": "/mentor/dashboard",
            "login_url": "/auth/mentor-login"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mentor login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Student login endpoint
@router.post("/student/login")
async def student_login(login_data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    try:
        logger.info(f"Student/Faculty login attempt for email: {login_data.username}")
        
        # First, check if user exists at all
        # Email-only lookup for existence
        any_user = db.query(User).filter(User.email == login_data.username).first()
        
        if any_user:
            logger.info(f"User found with role: {any_user.role}, user_type: {any_user.user_type}")
        else:
            logger.error(f"No user found with username/email: {login_data.username}")
        
        # Allow login with either username or email
        # Email-only login for students/faculty
        student = db.query(User).filter(
            (User.email == login_data.username),
            User.role.in_(["Student", "Faculty"])  # Allow both Student and Faculty to login here
        ).first()
        
        if not student:
            logger.error(f"Student/Faculty not found: {login_data.username}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
        if not verify_password(login_data.password, student.password_hash):
            logger.error(f"Invalid password for user: {login_data.username}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        logger.info(f"Student/Faculty login successful: {login_data.username}")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token_with_session(
            data={"sub": student.username, "role": student.role, "user_id": student.id}, 
            db=db,
            request=request,
            expires_delta=access_token_expires
        )
        
        log_student_action(
            student_id=student.id,
            student_username=student.username,
            action_type="LOGIN",
            resource_type="STUDENT_SESSION",
            details=f"Student login successful: {student.username}",
            ip_address=request.client.host if request.client else "127.0.0.1"
        )
        
        return {
            "access_token": access_token, 
            "token_type": "bearer", 
            "role": "Student",  # Always return Student role for dashboard access
            "user_id": student.id,
            "username": student.username,
            "email": student.email,
            "college": student.college,
            "department": student.department,
            "year": student.year,
            "github_link": student.github_link,
            "dashboard_url": "/student/dashboard",  # Both students and faculty use same dashboard
            "login_url": "/auth/student-login"
        }
    except HTTPException:
        # Re-raise HTTPExceptions (like 401) without converting to 500
        raise
    except Exception as e:
        logger.error(f"Student login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Logout endpoints for each role
# Helper to handle logout by invalidating session in DB
async def perform_logout(request: Request, db: Session):
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            session_token = payload.get("session_token")
            if session_token:
                SessionManager.invalidate_session(db, session_token)
                logger.info(f"Session {session_token} invalidated on logout")
        except JWTError:
            pass
        except Exception as e:
            logger.error(f"Logout session invalidation error: {str(e)}")

@router.post("/admin/logout")
async def admin_logout(request: Request, db: Session = Depends(get_db)):
    await perform_logout(request, db)
    return {"message": "Admin logged out successfully", "redirect_url": "/auth/admin-login"}

@router.post("/manager/logout")
async def manager_logout(request: Request, db: Session = Depends(get_db)):
    await perform_logout(request, db)
    return {"message": "Manager logged out successfully", "redirect_url": "/auth/manager-login"}

@router.post("/presenter/logout")
async def presenter_logout(request: Request, db: Session = Depends(get_db)):
    await perform_logout(request, db)
    return {"message": "Presenter logged out successfully", "redirect_url": "/auth/presenter-login"}

@router.post("/mentor/logout")
async def mentor_logout(request: Request, db: Session = Depends(get_db)):
    await perform_logout(request, db)
    return {"message": "Mentor logged out successfully", "redirect_url": "/auth/mentor-login"}

@router.post("/student/logout")
async def student_logout(request: Request, db: Session = Depends(get_db)):
    await perform_logout(request, db)
    return {"message": "Logged out successfully", "redirect_url": "/auth/student-login"}

# Dashboard endpoints for each role
@router.get("/admin/dashboard")
async def admin_dashboard():
    return {"dashboard": "admin", "title": "Admin Dashboard", "role": "Admin"}

@router.get("/manager/dashboard")
async def manager_dashboard():
    return {"dashboard": "manager", "title": "Manager Dashboard", "role": "Manager"}



@router.get("/mentor/dashboard")
async def mentor_dashboard():
    return {"dashboard": "mentor", "title": "Mentor Dashboard", "role": "Mentor"}

# @router.get("/student/dashboard")
# async def student_dashboard():
#     return {"dashboard": "student", "title": "Dashboard", "role": "Student"}

