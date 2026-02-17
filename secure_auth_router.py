from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db, User, Admin, Presenter, Mentor, Manager
from auth import verify_password, create_access_token_with_session, ACCESS_TOKEN_EXPIRE_MINUTES
from session_manager import SessionManager
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    username: str
    email: str
    role: str
    expires_in: int

@router.post("/secure-login", response_model=LoginResponse)
async def secure_login(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Secure login with single device enforcement"""
    try:
        user = None
        user_role = None
        
        # Check in different user tables
        for role, model in [
            ("Student", User),
            ("Admin", Admin), 
            ("Presenter", Presenter),
            ("Mentor", Mentor),
            ("Manager", Manager)
        ]:
            user_candidate = db.query(model).filter(model.username == login_data.username).first()
            if user_candidate:
                user = user_candidate
                user_role = role
                break
        
        if not user or not verify_password(login_data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        # Create token data
        token_data = {
            "sub": user.username,
            "role": user_role,
            "user_id": user.id
        }
        
        # Create access token with session management
        access_token = create_access_token_with_session(
            data=token_data,
            db=db,
            request=request,
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        logger.info(f"Secure login successful for {user.username} ({user_role}) from {request.client.host if request.client else 'unknown'}")
        
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user_id=user.id,
            username=user.username,
            email=user.email,
            role=user_role,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Secure login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")

@router.post("/logout")
async def logout(
    request: Request,
    db: Session = Depends(get_db)
):
    """Logout and invalidate current session"""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="No token provided")
        
        token = auth_header.split(" ")[1]
        
        # Decode token to get session info
        from jose import jwt
        from auth import SECRET_KEY, ALGORITHM
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        session_token = payload.get("session_token")
        
        if session_token:
            SessionManager.invalidate_session(db, session_token)
            logger.info(f"Session {session_token} invalidated on logout")
        
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return {"message": "Logged out"}

@router.get("/session-status")
async def check_session_status(
    request: Request,
    db: Session = Depends(get_db)
):
    """Check if current session is valid"""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return {"valid": False, "message": "No token provided"}
        
        token = auth_header.split(" ")[1]
        
        from jose import jwt, JWTError
        from auth import SECRET_KEY, ALGORITHM
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        user_type = payload.get("role")
        session_token = payload.get("session_token")
        
        if session_token and user_id and user_type:
            is_valid = SessionManager.validate_session(db, session_token, user_id, user_type)
            return {
                "valid": is_valid,
                "message": "Session valid" if is_valid else "Session invalid"
            }
        
        return {"valid": True, "message": "Token valid (no session management)"}
        
    except JWTError:
        return {"valid": False, "message": "Invalid token"}
    except Exception as e:
        logger.error(f"Session status check error: {str(e)}")
        return {"valid": False, "message": "Error checking session"}