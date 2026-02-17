from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

# Import Base from the main database module
try:
    from database import Base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()

class QuestionType(enum.Enum):
    TEXT = "TEXT"
    LONG_TEXT = "LONG_TEXT"
    RATING = "RATING"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    CHECKBOX = "CHECKBOX"

class FeedbackForm(Base):
    __tablename__ = "feedback_forms"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, nullable=False)  # Can reference sessions or cohort_course_sessions
    session_type = Column(String(20), default="global", nullable=False)  # global or cohort
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    is_anonymous = Column(Boolean, default=False)
    allow_multiple_submissions = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, nullable=False)  # User ID without foreign key constraint
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    questions = relationship("FeedbackQuestion", back_populates="form", cascade="all, delete-orphan")
    submissions = relationship("FeedbackSubmission", back_populates="form", cascade="all, delete-orphan")

class FeedbackQuestion(Base):
    __tablename__ = "feedback_questions"
    
    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("feedback_forms.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(Enum(QuestionType), nullable=False)
    options = Column(JSON, nullable=True)  # For MULTIPLE_CHOICE and CHECKBOX types
    is_required = Column(Boolean, default=True)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    form = relationship("FeedbackForm", back_populates="questions")
    answers = relationship("FeedbackAnswer", back_populates="question", cascade="all, delete-orphan")

class FeedbackSubmission(Base):
    __tablename__ = "feedback_submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("feedback_forms.id"), nullable=False)
    student_id = Column(Integer, nullable=True)  # Nullable for anonymous, no FK constraint
    session_id = Column(Integer, nullable=False)
    session_type = Column(String(20), nullable=False)
    is_anonymous = Column(Boolean, default=False)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    form = relationship("FeedbackForm", back_populates="submissions")
    answers = relationship("FeedbackAnswer", back_populates="submission", cascade="all, delete-orphan")

class FeedbackAnswer(Base):
    __tablename__ = "feedback_answers"
    
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("feedback_submissions.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("feedback_questions.id"), nullable=False)
    answer_text = Column(Text, nullable=True)  # For TEXT and LONG_TEXT
    answer_value = Column(Integer, nullable=True)  # For RATING (1-5)
    answer_choices = Column(JSON, nullable=True)  # For CHECKBOX (array of selected options)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    submission = relationship("FeedbackSubmission", back_populates="answers")
    question = relationship("FeedbackQuestion", back_populates="answers")
