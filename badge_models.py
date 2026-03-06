from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import sys
import os

# Add the current directory to sys.path to allow importing from database.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from database import Base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()

class BadgeConfiguration(Base):
    """
    Stores the rules and criteria for awarding a specific badge.
    """
    __tablename__ = "badge_configurations"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    level_id = Column(Integer, nullable=True)  # Associated level (e.g., Level 1, 2)
    cohort_id = Column(Integer, ForeignKey("cohorts.id"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    cohort_specific_course_id = Column(Integer, ForeignKey("cohort_specific_courses.id"), nullable=True)
    week_start = Column(Integer, nullable=False)
    week_end = Column(Integer, nullable=False)
    icon_url = Column(Text, nullable=True)
    
    # Criteria stored as JSON
    # Example: {"min_attendance": 80, "min_assignment_score": 70, "require_assignment_submission": true}
    criteria = Column(JSON, nullable=False)
    
    # List of keys from criteria that are mandatory
    # Example: ["min_attendance", "require_assignment_submission"]
    mandatory_checks = Column(JSON, nullable=False)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, nullable=True) # Admin ID

    awarded_badges = relationship("AwardedBadge", back_populates="configuration", cascade="all, delete-orphan")
    audit_logs = relationship("BadgeAuditLog", back_populates="configuration", cascade="all, delete-orphan")

class AwardedBadge(Base):
    """
    Records badges awarded to specific students.
    """
    __tablename__ = "awarded_badges"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    badge_config_id = Column(Integer, ForeignKey("badge_configurations.id"), nullable=False)
    awarded_at = Column(DateTime, default=datetime.utcnow)
    
    # Snapshot of the performance metrics that led to this award
    criteria_snapshot = Column(JSON, nullable=True)
    
    configuration = relationship("BadgeConfiguration", back_populates="awarded_badges")
    user = relationship("User")

class BadgeAuditLog(Base):
    """
    Tracks all badge evaluation attempts for audit and transparency.
    """
    __tablename__ = "badge_audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    badge_config_id = Column(Integer, ForeignKey("badge_configurations.id"), nullable=False)
    status = Column(String(50), nullable=False)  # ELIGIBLE, REJECTED, PENDING_CONFIRMATION
    
    # Detailed breakdown of performance vs criteria
    # Example: {"criteria_results": {"attendance": {"required": 80, "actual": 75, "pass": false}, ...}}
    details = Column(JSON, nullable=True)
    
    # Rejection reason or confirmation note
    remarks = Column(Text, nullable=True)
    
    evaluated_at = Column(DateTime, default=datetime.utcnow)
    
    configuration = relationship("BadgeConfiguration", back_populates="audit_logs")
    user = relationship("User")
