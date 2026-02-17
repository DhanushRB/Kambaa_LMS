"""
SMTP Configuration Models for LMS Email System
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class SMTPConfig(Base):
    __tablename__ = "smtp_config"
    
    id = Column(Integer, primary_key=True, index=True)
    smtp_host = Column(String(255), nullable=False)
    smtp_port = Column(Integer, nullable=False, default=587)
    smtp_username = Column(String(255), nullable=False)
    smtp_password = Column(Text, nullable=False)  # Encrypted
    smtp_from_email = Column(String(255), nullable=False)
    smtp_from_name = Column(String(255), default="Kambaa LMS")
    use_tls = Column(Boolean, default=True)
    use_ssl = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<SMTPConfig(host='{self.smtp_host}', from='{self.smtp_from_email}')>"