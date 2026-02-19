from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, JSON, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
import enum
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Admin(Base):
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class Presenter(Base):
    __tablename__ = "presenters"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    presenter_cohorts = relationship("PresenterCohort", back_populates="presenter")

class Manager(Base):
    __tablename__ = "managers"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="Student")
    college = Column(String(200), nullable=False)
    department = Column(String(100), nullable=False)
    year = Column(String(10), nullable=False)
    user_type = Column(String(20), nullable=False)  # Student or Faculty
    cohort_id = Column(Integer, ForeignKey("cohorts.id"), nullable=True)
    github_link = Column(String(500), nullable=True)
    
    # Faculty-specific fields
    experience = Column(Integer, nullable=True)  # Years of experience for faculty
    designation = Column(String(200), nullable=True)  # Faculty designation
    specialization = Column(String(500), nullable=True)  # Faculty specialization areas
    employment_type = Column(String(50), default="Full-time", nullable=True)  # Employment type
    joining_date = Column(DateTime, nullable=True)  # Faculty joining date
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    enrollments = relationship("Enrollment", back_populates="student")
    # submissions relationship moved to assignment_quiz_models.py
    current_cohort = relationship("Cohort")

class Course(Base):
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    duration_weeks = Column(Integer, default=12)
    sessions_per_week = Column(Integer, default=2)
    is_active = Column(Boolean, default=True)
    approval_status = Column(String(20), default='approved') # 'pending', 'approved', 'rejected'
    payment_type = Column(String(20), default='free') # 'free' or 'paid'
    default_price = Column(Float, default=0.0)
    instructor_id = Column(Integer, ForeignKey("users.id"))  # Legacy field, now managed by admin
    banner_image = Column(String(500), nullable=True) # URL or path to course banner image
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    instructor = relationship("User")  # Legacy relationship
    enrollments = relationship("Enrollment", back_populates="course")
    assignments = relationship("CourseAssignment", back_populates="course", cascade="all, delete-orphan")
    # assignments relationship moved to assignment_quiz_models.py
    modules = relationship("Module", back_populates="course")

class Enrollment(Base):
    __tablename__ = "enrollments"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    cohort_id = Column(Integer, ForeignKey("cohorts.id"), nullable=True)
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    progress = Column(Integer, default=0)
    payment_status = Column(String(20), default='not_required') # 'not_required', 'pending', 'paid'
    payment_amount = Column(Float, default=0.0)
    
    student = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")
    cohort = relationship("Cohort")

class CourseAssignment(Base):
    __tablename__ = "course_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    assignment_type = Column(String(50), nullable=False)  # 'all', 'individual', 'college', 'cohort'
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # For individual assignment
    college = Column(String(200), nullable=True)  # For college-wise assignment
    cohort_id = Column(Integer, ForeignKey("cohorts.id"), nullable=True)  # For cohort-wise assignment
    assigned_at = Column(DateTime, default=datetime.utcnow)
    assignment_mode = Column(String(50), default='free') # 'free' or 'paid'
    amount = Column(Float, default=0.0)
    assigned_by = Column(Integer, ForeignKey("admins.id"))
    
    course = relationship("Course", back_populates="assignments")
    user = relationship("User")
    cohort = relationship("Cohort")
    assigner = relationship("Admin")

# Assignment and Submission models moved to assignment_quiz_models.py

class Module(Base):
    __tablename__ = "modules"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    week_number = Column(Integer)
    title = Column(String(200))
    description = Column(Text)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    course = relationship("Course", back_populates="modules")
    sessions = relationship("Session", back_populates="module")
    forums = relationship("Forum", back_populates="module")

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("modules.id"))
    session_number = Column(Integer)
    title = Column(String(200))
    description = Column(Text)
    scheduled_time = Column(DateTime)
    duration_minutes = Column(Integer, default=120)
    zoom_link = Column(String(500))
    recording_url = Column(String(500))
    syllabus_content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    module = relationship("Module", back_populates="sessions")
    resources = relationship("Resource", back_populates="session")
    attendances = relationship("Attendance", back_populates="session")
    # quizzes relationship moved to assignment_quiz_models.py
    
SessionModel = Session

class Resource(Base):
    __tablename__ = "resources"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    title = Column(String(200))
    resource_type = Column(String(50))  # PDF, PPT, CODE, VIDEO, OTHER
    file_path = Column(String(500))
    file_size = Column(Integer, default=0)
    description = Column(Text)
    uploaded_by = Column(Integer, ForeignKey("admins.id"))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("Session", back_populates="resources")
    uploader = relationship("Admin")

class Attendance(Base):
    __tablename__ = "attendances"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    student_id = Column(Integer, ForeignKey("users.id"))
    attended = Column(Boolean, default=False)
    join_time = Column(DateTime)
    leave_time = Column(DateTime)
    duration_minutes = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("Session", back_populates="attendances")
    student = relationship("User")

# Quiz models moved to assignment_quiz_models.py

class Certificate(Base):
    __tablename__ = "certificates"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    certificate_url = Column(String(500))
    issued_by = Column(Integer, ForeignKey("admins.id"))
    issued_at = Column(DateTime, default=datetime.utcnow)
    
    student = relationship("User")
    course = relationship("Course")
    issuer = relationship("Admin")

class Forum(Base):
    __tablename__ = "forums"
    
    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("modules.id"))
    title = Column(String(200))
    description = Column(Text)
    is_pinned = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("admins.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    module = relationship("Module", back_populates="forums")
    creator = relationship("Admin")
    posts = relationship("ForumPost", back_populates="forum")

class ForumPost(Base):
    __tablename__ = "forum_posts"
    
    id = Column(Integer, primary_key=True, index=True)
    forum_id = Column(Integer, ForeignKey("forums.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    forum = relationship("Forum", back_populates="posts")
    user = relationship("User")

class SessionContent(Base):
    __tablename__ = "session_contents"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    content_type = Column(String(50))  # VIDEO, QUIZ, MATERIAL, MEETING_LINK
    title = Column(String(200))
    description = Column(Text)
    file_path = Column(String(500))
    file_type = Column(String(50))  # MP4, PDF, DOCX, etc.
    file_size = Column(Integer)
    content_data = Column(Text)  # JSON string for quiz data, etc.
    meeting_url = Column(String(500))  # For meeting links
    scheduled_time = Column(DateTime)  # For meeting links
    uploaded_by = Column(Integer, ForeignKey("admins.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("Session")
    uploader = relationship("Admin")

class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    date = Column(DateTime, nullable=False)
    event_type = Column(String(50), default="general")
    created_by = Column(Integer, ForeignKey("admins.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    creator = relationship("Admin")

class SystemSettings(Base):
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    setting_key = Column(String(100), unique=True, nullable=False)
    setting_value = Column(Text, nullable=False)  # JSON string
    setting_category = Column(String(50), nullable=False)  # system, email, security, backup
    updated_by = Column(Integer, ForeignKey("admins.id"))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    updater = relationship("Admin")

class Cohort(Base):
    __tablename__ = "cohorts"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    instructor_name = Column(String(200))  # Optional instructor name
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("admins.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    creator = relationship("Admin")
    user_cohorts = relationship("UserCohort", back_populates="cohort")

    cohort_courses = relationship("CohortCourse", back_populates="cohort")
    presenter_cohorts = relationship("PresenterCohort", back_populates="cohort")


class UserCohort(Base):
    __tablename__ = "user_cohorts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    cohort_id = Column(Integer, ForeignKey("cohorts.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    assigned_by = Column(Integer, ForeignKey("admins.id"))
    
    user = relationship("User")
    cohort = relationship("Cohort", back_populates="user_cohorts")
    assigner = relationship("Admin")

class StudentSessionStatus(Base):
    __tablename__ = "student_session_statuses"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(Integer)  # Can reference either sessions or cohort_course_sessions
    session_type = Column(String(20), default="global")  # "global" or "cohort"
    status = Column(String(20), default="Not Started")  # Not Started, Started, Completed, Not Attended
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    progress_percentage = Column(Float, default=0.0)
    
    student = relationship("User")

class StudentModuleStatus(Base):
    __tablename__ = "student_module_statuses"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    module_id = Column(Integer)  # Can reference either modules or cohort_course_modules
    module_type = Column(String(20), default="global")  # "global" or "cohort"
    status = Column(String(20), default="Not Started")  # Not Started, Started, Completed
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    progress_percentage = Column(Float, default=0.0)
    
    student = relationship("User")


class CohortCourse(Base):
    __tablename__ = "cohort_courses"
    
    id = Column(Integer, primary_key=True, index=True)
    cohort_id = Column(Integer, ForeignKey("cohorts.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    assigned_by = Column(Integer, ForeignKey("admins.id"))
    
    cohort = relationship("Cohort", back_populates="cohort_courses")
    course = relationship("Course")
    assigner = relationship("Admin")

class AdminLog(Base):
    __tablename__ = "admin_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("admins.id"))
    admin_username = Column(String(255))
    action_type = Column(String(50), nullable=False)
    resource_type = Column(String(100))
    resource_id = Column(Integer)
    details = Column(Text)
    ip_address = Column(String(45))
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    admin = relationship("Admin")

class PresenterLog(Base):
    __tablename__ = "presenter_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    presenter_id = Column(Integer, ForeignKey("presenters.id"))
    presenter_username = Column(String(255))
    action_type = Column(String(50), nullable=False)
    resource_type = Column(String(100))
    resource_id = Column(Integer)
    details = Column(Text)
    ip_address = Column(String(45))
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    presenter = relationship("Presenter")

class Mentor(Base):
    __tablename__ = "mentors"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class MentorCohort(Base):
    __tablename__ = "mentor_cohorts"
    
    id = Column(Integer, primary_key=True, index=True)
    mentor_id = Column(Integer, ForeignKey("mentors.id", ondelete="CASCADE"), nullable=False)
    cohort_id = Column(Integer, ForeignKey("cohorts.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    assigned_by = Column(Integer, ForeignKey("admins.id"))
    
    mentor = relationship("Mentor")
    cohort = relationship("Cohort")
    assigner = relationship("Admin")

class MentorCourse(Base):
    __tablename__ = "mentor_courses"
    
    id = Column(Integer, primary_key=True, index=True)
    mentor_id = Column(Integer, ForeignKey("mentors.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    cohort_id = Column(Integer, ForeignKey("cohorts.id", ondelete="CASCADE"), nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    assigned_by = Column(Integer, ForeignKey("admins.id"))
    
    mentor = relationship("Mentor")
    course = relationship("Course")
    cohort = relationship("Cohort")
    assigner = relationship("Admin")

class MentorSession(Base):
    __tablename__ = "mentor_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    mentor_id = Column(Integer, ForeignKey("mentors.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=True)
    cohort_id = Column(Integer, ForeignKey("cohorts.id", ondelete="CASCADE"), nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    assigned_by = Column(Integer, ForeignKey("admins.id"))
    
    mentor = relationship("Mentor")
    session = relationship("Session")
    course = relationship("Course")
    cohort = relationship("Cohort")
    assigner = relationship("Admin")

class MentorLog(Base):
    __tablename__ = "mentor_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    mentor_id = Column(Integer, ForeignKey("mentors.id", ondelete="CASCADE"))
    mentor_username = Column(String(255))
    action_type = Column(String(50))
    resource_type = Column(String(50))
    resource_id = Column(Integer)
    details = Column(Text)
    ip_address = Column(String(45))
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    mentor = relationship("Mentor")

class PresenterCohort(Base):
    __tablename__ = "presenter_cohorts"
    
    id = Column(Integer, primary_key=True, index=True)
    presenter_id = Column(Integer, ForeignKey("presenters.id", ondelete="CASCADE"), nullable=False)
    cohort_id = Column(Integer, ForeignKey("cohorts.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    assigned_by = Column(Integer, ForeignKey("admins.id"))
    
    presenter = relationship("Presenter")
    cohort = relationship("Cohort")
    assigner = relationship("Admin")

class StudentLog(Base):
    __tablename__ = "student_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    student_username = Column(String(255))
    action_type = Column(String(50), nullable=False)
    resource_type = Column(String(100))
    resource_id = Column(Integer)
    details = Column(Text)
    ip_address = Column(String(45))
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    student = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(20), default="info")  # info, success, warning, error
    is_read = Column(Boolean, default=False, nullable=False)
    action_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    email = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    status = Column(String(20), default="sent")  # sent, failed
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    email_enabled = Column(Boolean, default=True, nullable=False)
    in_app_enabled = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")

# Email Campaign Tables
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

# Chat System Models
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
    created_by = Column(Integer, ForeignKey("admins.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    participants = relationship("ChatParticipant", back_populates="chat")
    messages = relationship("Message", back_populates="chat")
    creator = relationship("Admin")

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

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

# Session Meeting Model
class SessionMeeting(Base):
    __tablename__ = "session_meetings"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    meeting_datetime = Column(DateTime, nullable=True)  # Allow null for unscheduled meetings
    duration_minutes = Column(Integer, default=60)
    meeting_url = Column(String(500), nullable=True)
    location = Column(String(500), nullable=True)
    status = Column(String(20), default="scheduled")  # scheduled, completed, cancelled
    
    created_by = Column(Integer, ForeignKey("admins.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    session = relationship("Session")
    creator = relationship("Admin")
    calendar_event = relationship("CalendarEvent", back_populates="session_meeting", uselist=False)

# Calendar Events Model (General events only - no meeting type)
class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=True)
    event_type = Column(String(50), default="general", nullable=False)  # general, exam, holiday (no meeting)
    location = Column(String(500), nullable=True)
    is_all_day = Column(Boolean, default=False)
    
    # Links
    course_id = Column(Integer, nullable=True)
    session_meeting_id = Column(Integer, ForeignKey("session_meetings.id"), nullable=True)  # Auto-created from meetings
    
    reminder_minutes = Column(Integer, default=15)
    is_auto_generated = Column(Boolean, default=False)  # True for session meetings
    
    # Creator tracking
    created_by_admin_id = Column(Integer, nullable=True)
    created_by_presenter_id = Column(Integer, nullable=True) 
    created_by_mentor_id = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    session_meeting = relationship("SessionMeeting", back_populates="calendar_event")

class PasswordResetOTP(Base):
    __tablename__ = "password_reset_otps"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(200), index=True, nullable=False)
    otp = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

# Import chat models to ensure they're included
from chat_models import Chat as ChatModel, ChatParticipant as ChatParticipantModel, Message as MessageModel

# Import cohort-specific models to ensure they're included
from cohort_specific_models import CohortSpecificCourse, CohortCourseModule, CohortCourseSession, CohortCourseResource

# Import session models for single device login
from session_models import UserSession

Base.metadata.create_all(bind=engine)