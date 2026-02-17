from database import Base, User
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

class ApprovalStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class OperationType(enum.Enum):
    DELETE = "delete"
    UNPUBLISH = "unpublish"
    DISABLE = "disable"
    ARCHIVE = "archive"
    BULK_UPDATE = "bulk_update"
    FINAL_MODIFICATION = "final_modification"
    CREATE = "create"

class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, nullable=False)  # Remove FK constraint for now
    operation_type = Column(Enum(OperationType), nullable=False)
    target_entity_type = Column(String(50), nullable=False)  # course, cohort, user, etc.
    target_entity_id = Column(Integer, nullable=False)
    target_entity_data = Column(Text)  # JSON data of the entity before operation
    operation_data = Column(Text)  # JSON data of the requested operation
    reason = Column(Text)
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING)
    approved_by = Column(Integer, nullable=True)  # Remove FK constraint for now
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EntityStatus(Base):
    __tablename__ = "entity_status"
    
    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    status = Column(String(50), default="active")  # active, pending_approval, disabled
    approval_request_id = Column(Integer, ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)