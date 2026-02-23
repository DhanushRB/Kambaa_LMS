from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, JSON, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

# Import Base from the main database module
try:
    from database import Base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()

class SubmissionType(enum.Enum):
    FILE = "FILE"
    TEXT = "TEXT"
    BOTH = "BOTH"

class QuestionType(enum.Enum):
    MCQ = "MCQ"
    TRUE_FALSE = "TRUE_FALSE"
    SHORT_ANSWER = "SHORT_ANSWER"

class AssignmentStatus(enum.Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    EVALUATED = "EVALUATED"

class QuizStatus(enum.Enum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

# Assignment Models
class Assignment(Base):
    __tablename__ = "assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, nullable=False)  # Can reference sessions or cohort_course_sessions
    session_type = Column(String(20), default="global", nullable=False)  # global or cohort
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    instructions = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)  # Assignment file (PDF/DOC/ZIP)
    submission_type = Column(Enum(SubmissionType), default=SubmissionType.FILE)
    start_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=False)
    total_marks = Column(Integer, default=100)
    evaluation_criteria = Column(Text, nullable=True)
    created_by = Column(Integer, nullable=False)  # Admin/Presenter ID
    created_by_type = Column(String(20), default="admin")  # admin, presenter
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    due_reminder_sent = Column(Boolean, default=False)
    
    # Relationships - Note: session relationship is conditional based on session_type
    # session = relationship("Session")  # Commented out due to dual session type support
    submissions = relationship("AssignmentSubmission", back_populates="assignment")
    grades = relationship("AssignmentGrade", back_populates="assignment")

class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    submission_text = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    file_name = Column(String(200), nullable=True)
    file_size = Column(Integer, nullable=True)
    status = Column(Enum(AssignmentStatus), default=AssignmentStatus.SUBMITTED)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    assignment = relationship("Assignment", back_populates="submissions")
    student = relationship("User")
    grade = relationship("AssignmentGrade", back_populates="submission", uselist=False)

class AssignmentGrade(Base):
    __tablename__ = "assignment_grades"
    
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    submission_id = Column(Integer, ForeignKey("assignment_submissions.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    marks_obtained = Column(Float, nullable=False)
    total_marks = Column(Integer, nullable=False)
    percentage = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    graded_by = Column(Integer, nullable=False)  # Admin/Presenter/Mentor ID
    graded_by_type = Column(String(20), default="admin")  # admin, presenter, mentor
    graded_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    assignment = relationship("Assignment", back_populates="grades")
    submission = relationship("AssignmentSubmission", back_populates="grade")
    student = relationship("User")

# Quiz Models
class Quiz(Base):
    __tablename__ = "quizzes"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, nullable=False)  # Can reference sessions or cohort_course_sessions
    session_type = Column(String(20), default="global", nullable=False)  # global or cohort
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    time_limit_minutes = Column(Integer, nullable=True)  # NULL for no time limit
    total_marks = Column(Integer, default=100)
    auto_submit = Column(Boolean, default=True)  # Auto-submit on time expiry
    created_by = Column(Integer, nullable=False)  # Admin/Presenter ID
    created_by_type = Column(String(20), default="admin")  # admin, presenter
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships - Note: session relationship is conditional based on session_type
    # session = relationship("Session")  # Commented out due to dual session type support
    questions = relationship("QuizQuestion", back_populates="quiz")
    attempts = relationship("QuizAttempt", back_populates="quiz")
    results = relationship("QuizResult", back_populates="quiz")

class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    
    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(Enum(QuestionType), nullable=False)
    options = Column(JSON, nullable=True)  # For MCQ: ["Option A", "Option B", ...]
    correct_answer = Column(Text, nullable=False)  # For MCQ: option index, for others: text
    marks = Column(Integer, default=1)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    quiz = relationship("Quiz", back_populates="questions")

class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(QuizStatus), default=QuizStatus.IN_PROGRESS)
    started_at = Column(DateTime, default=datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)
    time_taken_minutes = Column(Integer, nullable=True)
    auto_submitted = Column(Boolean, default=False)
    
    # Relationships
    quiz = relationship("Quiz", back_populates="attempts")
    student = relationship("User")
    answers = relationship("QuizAnswer", back_populates="attempt")
    result = relationship("QuizResult", back_populates="attempt", uselist=False)

class QuizAnswer(Base):
    __tablename__ = "quiz_answers"
    
    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("quiz_attempts.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("quiz_questions.id"), nullable=False)
    answer_text = Column(Text, nullable=True)
    selected_option = Column(Integer, nullable=True)  # For MCQ
    is_correct = Column(Boolean, nullable=True)  # Auto-calculated for objective questions
    marks_obtained = Column(Float, default=0)
    
    # Relationships
    attempt = relationship("QuizAttempt", back_populates="answers")
    question = relationship("QuizQuestion")

class QuizResult(Base):
    __tablename__ = "quiz_results"
    
    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    attempt_id = Column(Integer, ForeignKey("quiz_attempts.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total_marks = Column(Integer, nullable=False)
    marks_obtained = Column(Float, nullable=False)
    percentage = Column(Float, nullable=False)
    grade = Column(String(5), nullable=True)  # A+, A, B+, etc.
    auto_evaluated = Column(Boolean, default=True)
    evaluated_by = Column(Integer, nullable=True)  # For manual evaluation
    evaluated_by_type = Column(String(20), nullable=True)  # admin, presenter, mentor
    evaluated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    quiz = relationship("Quiz", back_populates="results")
    attempt = relationship("QuizAttempt", back_populates="result")
    student = relationship("User")