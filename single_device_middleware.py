from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from database import get_db
from session_manager import SessionManager
from jose import jwt, JWTError
from auth import SECRET_KEY, ALGORITHM
import logging

logger = logging.getLogger(__name__)

class SingleDeviceMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce single device login for students"""
    
    def __init__(self, app, enforce_for_roles=None):
        super().__init__(app)
        # Default to enforce only for Students
        self.enforce_for_roles = enforce_for_roles or ["Student"]
    
    async def dispatch(self, request: Request, call_next):
        # Skip middleware for certain paths
        skip_paths = [
            "/docs", "/redoc", "/openapi.json", "/health", 
            "/api/auth/secure-login", "/api/auth/logout", "/api/auth/session-status",
            "/auth/register", "/", "/uploads"
        ]
        
        # Skip if path should be ignored
        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)
        
        # Skip if not a protected API route
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return await call_next(request)
        
        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            
            user_id = payload.get("user_id")
            user_type = payload.get("role")
            session_token = payload.get("session_token")
            
            # Only enforce for specified roles
            if user_type not in self.enforce_for_roles:
                return await call_next(request)
            
            # Skip if no session management data
            if not (session_token and user_id and user_type):
                return await call_next(request)
            
            # Validate session
            db = next(get_db())
            try:
                is_valid = SessionManager.validate_session(db, session_token, user_id, user_type)
                if not is_valid:
                    logger.warning(f"Invalid session detected for user {user_id} ({user_type})")
                    return JSONResponse(
                        status_code=401,
                        content={
                            "detail": "Your session has expired or you have been logged in from another device. Please login again.",
                            "error_code": "SESSION_INVALID"
                        }
                    )
            finally:
                db.close()
            
        except JWTError:
            # Invalid token, let the normal auth flow handle it
            pass
        except Exception as e:
            logger.error(f"Session validation error: {str(e)}")
            # Don't block request on middleware errors
            pass
        
        return await call_next(request)