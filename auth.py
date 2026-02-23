from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db, User, Admin, Presenter, Mentor, Manager
from session_manager import SessionManager
import os
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token_with_session(data: dict, db: Session, request: Request = None, expires_delta: Optional[timedelta] = None):
    """Create access token with session management for single device login"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    # Create session token for single device enforcement
    user_id = data.get("user_id")
    user_type = data.get("role")
    
    if user_id and user_type:
        device_info = None
        ip_address = None
        
        if request:
            device_info = request.headers.get("user-agent", "Unknown")
            ip_address = request.client.host if request.client else "Unknown"
        
        # Create session and get session token
        session_token = SessionManager.create_session(
            db=db,
            user_id=user_id,
            user_type=user_type,
            device_info=device_info,
            ip_address=ip_address
        )
        
        # Add session token to JWT payload
        to_encode.update({"session_token": session_token})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Original create_access_token for backward compatibility"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token_with_session(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Verify token and validate session for single device enforcement"""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        user_type: str = payload.get("role")
        session_token: str = payload.get("session_token")
        
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Validate session if session_token exists (for single device enforcement)
        if session_token and user_id and user_type:
            is_valid = SessionManager.validate_session(db, session_token, user_id, user_type)
            if not is_valid:
                logger.warning(f"Invalid session for user {user_id} ({user_type}): {session_token}")
                raise HTTPException(
                    status_code=401, 
                    detail="Session expired or invalid. Please login again."
                )
        
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Original verify_token for backward compatibility"""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(token_data: dict = Depends(verify_token_with_session), db: Session = Depends(get_db)):
    username = token_data.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token: no username")

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail=f"User not found: {username}")
    return user

def get_current_student(current_user: User = Depends(get_current_user)):
    if current_user.role == "Student" and not current_user.github_link:
        raise HTTPException(status_code=403, detail="Please update your GitHub link in profile to access this page")
    return current_user

def get_current_admin(token_data: dict = Depends(verify_token_with_session), db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == token_data.get("sub")).first()
    if admin is None:
        raise HTTPException(status_code=401, detail="Admin not found")
    return admin

def get_current_presenter(token_data: dict = Depends(verify_token_with_session), db: Session = Depends(get_db)):
    presenter = db.query(Presenter).filter(Presenter.username == token_data.get("sub")).first()
    if presenter is None:
        raise HTTPException(status_code=401, detail="Presenter not found")
    return presenter

def get_current_mentor(token_data: dict = Depends(verify_token_with_session), db: Session = Depends(get_db)):
    mentor = db.query(Mentor).filter(Mentor.username == token_data.get("sub")).first()
    if mentor is None:
        raise HTTPException(status_code=401, detail="Mentor not found")
    return mentor

def get_current_manager(token_data: dict = Depends(verify_token_with_session), db: Session = Depends(get_db)):
    manager = db.query(Manager).filter(Manager.username == token_data.get("sub")).first()
    if manager is None:
        raise HTTPException(status_code=401, detail="Manager not found")
    return manager

def get_current_user_any_role(token_data: dict = Depends(verify_token_with_session), db: Session = Depends(get_db)):
    """Get current user of any role (Student, Admin, Presenter, Mentor, Manager)"""
    username = token_data.get("sub")
    role = token_data.get("role")
    
    if role == "Student":
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=401, detail="Student not found")
        return {"id": user.id, "username": user.username, "email": user.email, "role": "Student"}
    elif role == "Admin":
        admin = db.query(Admin).filter(Admin.username == username).first()
        if not admin:
            raise HTTPException(status_code=401, detail="Admin not found")
        return {"id": admin.id, "username": admin.username, "email": admin.email, "role": "Admin"}
    elif role == "Presenter":
        presenter = db.query(Presenter).filter(Presenter.username == username).first()
        if not presenter:
            raise HTTPException(status_code=401, detail="Presenter not found")
        return {"id": presenter.id, "username": presenter.username, "email": presenter.email, "role": "Presenter"}
    elif role == "Mentor":
        mentor = db.query(Mentor).filter(Mentor.username == username).first()
        if not mentor:
            raise HTTPException(status_code=401, detail="Mentor not found")
        return {"id": mentor.id, "username": mentor.username, "email": mentor.email, "role": "Mentor"}
    elif role == "Manager":
        manager = db.query(Manager).filter(Manager.username == username).first()
        if not manager:
            raise HTTPException(status_code=401, detail="Manager not found")
        return {"id": manager.id, "username": manager.username, "email": manager.email, "role": "Manager"}
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

def get_current_admin_presenter_mentor_or_manager(token_data: dict = Depends(verify_token_with_session), db: Session = Depends(get_db)):
    """Get current admin, presenter, mentor, or manager - all have calendar access permissions"""
    username = token_data.get("sub")
    role = token_data.get("role")
    
    if role == "Admin":
        admin = db.query(Admin).filter(Admin.username == username).first()
        if not admin:
            raise HTTPException(status_code=401, detail="Admin not found")
        return {"id": admin.id, "username": admin.username, "email": admin.email, "role": "Admin"}
    elif role == "Presenter":
        presenter = db.query(Presenter).filter(Presenter.username == username).first()
        if not presenter:
            raise HTTPException(status_code=401, detail="Presenter not found")
        return {"id": presenter.id, "username": presenter.username, "email": presenter.email, "role": "Presenter"}
    elif role == "Mentor":
        mentor = db.query(Mentor).filter(Mentor.username == username).first()
        if not mentor:
            raise HTTPException(status_code=401, detail="Mentor not found")
        return {"id": mentor.id, "username": mentor.username, "email": mentor.email, "role": "Mentor"}
    elif role == "Manager":
        manager = db.query(Manager).filter(Manager.username == username).first()
        if not manager:
            raise HTTPException(status_code=401, detail="Manager not found")
        return {"id": manager.id, "username": manager.username, "email": manager.email, "role": "Manager"}
    else:
        raise HTTPException(status_code=403, detail="Access denied. Admin, Presenter, Mentor, or Manager role required.")

def get_current_admin_presenter_or_mentor(token_data: dict = Depends(verify_token_with_session), db: Session = Depends(get_db)):
    """Get current admin, presenter, or mentor - all have event creation permissions"""
    username = token_data.get("sub")
    role = token_data.get("role")
    
    if role == "Admin":
        admin = db.query(Admin).filter(Admin.username == username).first()
        if not admin:
            raise HTTPException(status_code=401, detail="Admin not found")
        return admin
    elif role == "Presenter":
        presenter = db.query(Presenter).filter(Presenter.username == username).first()
        if not presenter:
            raise HTTPException(status_code=401, detail="Presenter not found")
        return presenter
    elif role == "Mentor":
        mentor = db.query(Mentor).filter(Mentor.username == username).first()
        if not mentor:
            raise HTTPException(status_code=401, detail="Mentor not found")
        return mentor
    else:
        raise HTTPException(status_code=403, detail="Access denied. Admin, Presenter, or Mentor role required.")

def get_current_admin_or_presenter(token_data: dict = Depends(verify_token_with_session), db: Session = Depends(get_db)):
    """Get current admin, manager, or presenter - all have course management permissions"""
    username = token_data.get("sub")
    role = token_data.get("role")
    
    if role == "Admin":
        admin = db.query(Admin).filter(Admin.username == username).first()
        if not admin:
            raise HTTPException(status_code=401, detail="Admin not found")
        return admin
    elif role == "Manager":
        manager = db.query(Manager).filter(Manager.username == username).first()
        if not manager:
            raise HTTPException(status_code=401, detail="Manager not found")
        return manager
    elif role == "Presenter":
        presenter = db.query(Presenter).filter(Presenter.username == username).first()
        if not presenter:
            raise HTTPException(status_code=401, detail="Presenter not found")
        return presenter
    else:
        raise HTTPException(status_code=403, detail="Access denied. Admin, Manager, or Presenter role required.")

def require_role(required_role: str):
    def role_checker(current_user: User = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        if current_user.role != required_role:
            raise HTTPException(status_code=403, detail=f"Insufficient permissions. Required: {required_role}, Got: {current_user.role}")
        return current_user
    return role_checker

def get_current_user_from_token(token: str, db: Session):
    """Get user from token string (for direct token usage)"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            # Try admin table
            admin = db.query(Admin).filter(Admin.username == username).first()
            if admin is None:
                # Try presenter table
                presenter = db.query(Presenter).filter(Presenter.username == username).first()
                if presenter is None:
                    # Try mentor table
                    mentor = db.query(Mentor).filter(Mentor.username == username).first()
                    if mentor is None:
                        # Try manager table
                        manager = db.query(Manager).filter(Manager.username == username).first()
                        if manager is None:
                            raise HTTPException(status_code=401, detail="User not found")
                        return manager
                    return mentor
                return presenter
            return admin
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user_info(token_data: dict = Depends(verify_token_with_session), db: Session = Depends(get_db)):
    """Get current user info from any user type for chat system"""
    username = token_data.get("sub")
    role = token_data.get("role")
    user_id = token_data.get("user_id")
    
    if role == "Admin":
        user = db.query(Admin).filter(Admin.username == username).first()
    elif role == "Presenter":
        user = db.query(Presenter).filter(Presenter.username == username).first()
    elif role == "Mentor":
        user = db.query(Mentor).filter(Mentor.username == username).first()
    elif role == "Manager":
        user = db.query(Manager).filter(Manager.username == username).first()
    elif role == "Student":
        user = db.query(User).filter(User.username == username).first()
    else:
        raise HTTPException(status_code=401, detail="Invalid user role")
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": role
    }