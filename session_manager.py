from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from session_models import UserSession
import uuid
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    @staticmethod
    def create_session(db: Session, user_id: int, user_type: str, device_info: str = None, ip_address: str = None):
        """Create new session and invalidate all existing sessions for the user"""
        try:
            # Invalidate all existing active sessions for this user
            existing_sessions = db.query(UserSession).filter(
                UserSession.user_id == user_id,
                UserSession.user_type == user_type,
                UserSession.is_active == True
            ).all()
            
            for session in existing_sessions:
                session.is_active = False
                logger.info(f"Invalidated session {session.session_token} for user {user_id}")
            
            # Create new session
            session_token = str(uuid.uuid4())
            new_session = UserSession(
                user_id=user_id,
                user_type=user_type,
                session_token=session_token,
                device_info=device_info,
                ip_address=ip_address
            )
            
            db.add(new_session)
            db.commit()
            
            logger.info(f"Created new session {session_token} for user {user_id} ({user_type})")
            return session_token
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create session: {str(e)}")
            raise
    
    @staticmethod
    def validate_session(db: Session, session_token: str, user_id: int, user_type: str):
        """Validate if session is active and belongs to the user"""
        try:
            session = db.query(UserSession).filter(
                UserSession.session_token == session_token,
                UserSession.user_id == user_id,
                UserSession.user_type == user_type,
                UserSession.is_active == True
            ).first()
            
            if session:
                # Update last activity
                session.last_activity = datetime.utcnow()
                db.commit()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to validate session: {str(e)}")
            return False
    
    @staticmethod
    def invalidate_session(db: Session, session_token: str):
        """Invalidate a specific session"""
        try:
            session = db.query(UserSession).filter(
                UserSession.session_token == session_token,
                UserSession.is_active == True
            ).first()
            
            if session:
                session.is_active = False
                db.commit()
                logger.info(f"Invalidated session {session_token}")
                return True
            
            return False
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to invalidate session: {str(e)}")
            return False
    
    @staticmethod
    def cleanup_expired_sessions(db: Session, hours: int = 24):
        """Clean up sessions older than specified hours"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            expired_sessions = db.query(UserSession).filter(
                UserSession.last_activity < cutoff_time
            ).all()
            
            for session in expired_sessions:
                session.is_active = False
            
            db.commit()
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to cleanup expired sessions: {str(e)}")
    
    @staticmethod
    def get_active_sessions(db: Session, user_id: int, user_type: str):
        """Get all active sessions for a user"""
        try:
            sessions = db.query(UserSession).filter(
                UserSession.user_id == user_id,
                UserSession.user_type == user_type,
                UserSession.is_active == True
            ).all()
            
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to get active sessions: {str(e)}")
            return []