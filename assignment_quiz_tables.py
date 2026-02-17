from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, JSON, Enum, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import enum
import os
from dotenv import load_dotenv

load_dotenv()

# Create separate Base for assignment/quiz models to avoid conflicts
AssignmentQuizBase = declarative_base()

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
class Assignment(AssignmentQuizBase):
    __tablename__ = "assignments"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, nullable=False)  # Remove ForeignKey for now
    session_type = Column(String(20), default="global") # global, cohort
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

class AssignmentSubmission(AssignmentQuizBase):
    __tablename__ = "assignment_submissions"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, nullable=False)  # Remove ForeignKey for now
    student_id = Column(Integer, nullable=False)  # Remove ForeignKey for now
    submission_text = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    file_name = Column(String(200), nullable=True)
    file_size = Column(Integer, nullable=True)
    status = Column(Enum(AssignmentStatus), default=AssignmentStatus.SUBMITTED)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AssignmentGrade(AssignmentQuizBase):
    __tablename__ = "assignment_grades"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, nullable=False)
    submission_id = Column(Integer, nullable=False)
    student_id = Column(Integer, nullable=False)
    marks_obtained = Column(Float, nullable=False)
    total_marks = Column(Integer, nullable=False)
    percentage = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    graded_by = Column(Integer, nullable=False)  # Admin/Presenter/Mentor ID
    graded_by_type = Column(String(20), default="admin")  # admin, presenter, mentor
    graded_at = Column(DateTime, default=datetime.utcnow)

# Quiz Models
class Quiz(AssignmentQuizBase):
    __tablename__ = "quizzes"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, nullable=False)  # Remove ForeignKey for now
    session_type = Column(String(20), default="global") # global, cohort
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

class QuizQuestion(AssignmentQuizBase):
    __tablename__ = "quiz_questions"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(Enum(QuestionType), nullable=False)
    options = Column(JSON, nullable=True)  # For MCQ: ["Option A", "Option B", ...]
    correct_answer = Column(Text, nullable=False)  # For MCQ: option index, for others: text
    marks = Column(Integer, default=1)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class QuizAttempt(AssignmentQuizBase):
    __tablename__ = "quiz_attempts"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, nullable=False)
    student_id = Column(Integer, nullable=False)
    status = Column(Enum(QuizStatus), default=QuizStatus.IN_PROGRESS)
    started_at = Column(DateTime, default=datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)
    time_taken_minutes = Column(Integer, nullable=True)
    auto_submitted = Column(Boolean, default=False)

class QuizAnswer(AssignmentQuizBase):
    __tablename__ = "quiz_answers"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, nullable=False)
    question_id = Column(Integer, nullable=False)
    answer_text = Column(Text, nullable=True)
    selected_option = Column(Integer, nullable=True)  # For MCQ
    is_correct = Column(Boolean, nullable=True)  # Auto-calculated for objective questions
    marks_obtained = Column(Float, default=0)

class QuizResult(AssignmentQuizBase):
    __tablename__ = "quiz_results"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, nullable=False)
    attempt_id = Column(Integer, nullable=False)
    student_id = Column(Integer, nullable=False)
    total_marks = Column(Integer, nullable=False)
    marks_obtained = Column(Float, nullable=False)
    percentage = Column(Float, nullable=False)
    grade = Column(String(5), nullable=True)  # A+, A, B+, etc.
    auto_evaluated = Column(Boolean, default=True)
    evaluated_by = Column(Integer, nullable=True)  # For manual evaluation
    evaluated_by_type = Column(String(20), nullable=True)  # admin, presenter, mentor
    evaluated_at = Column(DateTime, default=datetime.utcnow)

# Create tables if they don't exist
if __name__ == "__main__":
    DATABASE_URL = os.getenv("DATABASE_URL")
    if DATABASE_URL:
        engine = create_engine(DATABASE_URL)
        AssignmentQuizBase.metadata.create_all(bind=engine)
        print("Assignment and Quiz tables created successfully!")