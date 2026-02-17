from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class ResourceView(Base):
    __tablename__ = "resource_views"
    
    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, nullable=False)  # Removed foreign key constraint
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    viewed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    resource_type = Column(String(50), default="RESOURCE", nullable=True)  # Track resource type
    
    # Relationships (removed resource relationship due to removed FK)
    student = relationship("User")