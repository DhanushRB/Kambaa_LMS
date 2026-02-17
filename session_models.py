from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    user_type = Column(String(50), nullable=False)  # Student, Admin, Presenter, etc.
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    device_info = Column(String(500))  # Browser/device information
    ip_address = Column(String(45))  # IPv4 or IPv6
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<UserSession(user_id={self.user_id}, user_type={self.user_type}, active={self.is_active})>"