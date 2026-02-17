from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class EmailTemplate(Base):
    __tablename__ = "email_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    target_role = Column(String(50), nullable=False)  # Student, Admin, Presenter, All
    category = Column(String(100), default="general")
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("admins.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    creator = relationship("Admin")
    campaigns = relationship("EmailCampaign", back_populates="template")

class EmailCampaign(Base):
    __tablename__ = "email_campaigns"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    template_id = Column(Integer, ForeignKey("email_templates.id"))
    target_role = Column(String(50), nullable=False)
    status = Column(String(50), default="draft")  # draft, scheduled, sending, completed, failed
    scheduled_time = Column(DateTime, nullable=True)
    sent_count = Column(Integer, default=0)
    delivered_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    created_by = Column(Integer, ForeignKey("admins.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    template = relationship("EmailTemplate", back_populates="campaigns")
    creator = relationship("Admin")
    recipients = relationship("EmailRecipient", back_populates="campaign")

class EmailRecipient(Base):
    __tablename__ = "email_recipients"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    email = Column(String(255), nullable=False)
    status = Column(String(50), default="pending")  # pending, sent, delivered, failed, bounced
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    campaign = relationship("EmailCampaign", back_populates="recipients")
    user = relationship("User")

class EmailAnalytics(Base):
    __tablename__ = "email_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id"))
    metric_name = Column(String(100), nullable=False)  # sent, delivered, opened, clicked, bounced
    metric_value = Column(Integer, default=0)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    
    campaign = relationship("EmailCampaign")