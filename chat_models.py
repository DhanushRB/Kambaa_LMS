from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class ChatType(enum.Enum):
    SINGLE = "SINGLE"
    GROUP = "GROUP"

class MessageType(enum.Enum):
    TEXT = "TEXT"
    FILE = "FILE"
    LINK = "LINK"

class Chat(Base):
    __tablename__ = "chats"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=True)  # For group chats
    chat_type = Column(Enum(ChatType), nullable=False)
    created_by = Column(Integer, nullable=True)  # Removed FK constraint
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    participants = relationship("ChatParticipant", back_populates="chat")
    messages = relationship("Message", back_populates="chat")

class ChatParticipant(Base):
    __tablename__ = "chat_participants"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    user_id = Column(Integer, nullable=False)  # Can be from any user table
    user_type = Column(String(20), nullable=False)  # Admin, Presenter, Mentor, Student
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_read_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    chat = relationship("Chat", back_populates="participants")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    sender_id = Column(Integer, nullable=False)
    sender_type = Column(String(20), nullable=False)  # Admin, Presenter, Mentor, Student
    message_type = Column(Enum(MessageType), default=MessageType.TEXT)
    content = Column(Text, nullable=False)
    file_path = Column(String(500), nullable=True)
    file_name = Column(String(200), nullable=True)
    file_size = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime, nullable=True)
    
    # Relationships
    chat = relationship("Chat", back_populates="messages")