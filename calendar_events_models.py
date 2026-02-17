from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Enum, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class EventType(enum.Enum):
    GENERAL = "general"
    WORKSHOP = "workshop"
    WEBINAR = "webinar"
    EXAM = "exam"
    MEETING = "meeting"
    DEADLINE = "deadline"
    HOLIDAY = "holiday"

class AttendanceType(enum.Enum):
    ONLINE = "online"
    PHYSICAL = "physical"
    HYBRID = "hybrid"

class AttendanceStatus(enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"

class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime)
    event_type = Column(Enum(EventType), default=EventType.GENERAL)
    location = Column(String(500))
    is_all_day = Column(Boolean, default=False)
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String(100))  # JSON string for recurrence rules
    recurrence_end_date = Column(DateTime)
    
    # Relationships to existing entities
    course_id = Column(Integer, ForeignKey("courses.id"))
    session_id = Column(Integer, ForeignKey("sessions.id"))
    assignment_id = Column(Integer, ForeignKey("assignments.id"))
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    
    # Notification settings
    reminder_minutes = Column(Integer, default=15)
    send_email_reminder = Column(Boolean, default=True)
    send_push_notification = Column(Boolean, default=True)
    
    # Metadata
    created_by = Column(Integer, ForeignKey("admins.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    course = relationship("Course", back_populates="calendar_events")
    session = relationship("SessionModel", back_populates="calendar_events")
    assignment = relationship("Assignment", back_populates="calendar_events")
    quiz = relationship("Quiz", back_populates="calendar_events")
    creator = relationship("Admin")

class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), unique=True)
    attendance_type = Column(Enum(AttendanceType), default=AttendanceType.ONLINE)
    
    # Auto-tracking settings
    auto_track_enabled = Column(Boolean, default=True)
    track_join_time = Column(Boolean, default=True)
    track_leave_time = Column(Boolean, default=True)
    minimum_duration_minutes = Column(Integer, default=30)
    
    # Manual override settings
    allow_manual_override = Column(Boolean, default=True)
    manual_cutoff_hours = Column(Integer, default=24)
    
    # Location-based attendance (for physical/hybrid classes)
    require_geolocation = Column(Boolean, default=False)
    allowed_latitude = Column(Float)
    allowed_longitude = Column(Float)
    location_radius_meters = Column(Integer, default=100)
    
    # QR code attendance
    qr_code_enabled = Column(Boolean, default=False)
    qr_code_data = Column(String(500))
    qr_code_expires_at = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    session = relationship("SessionModel")
    attendance_records = relationship("EnhancedAttendance", back_populates="attendance_session")

class EnhancedAttendance(Base):
    __tablename__ = "enhanced_attendance"
    
    id = Column(Integer, primary_key=True, index=True)
    attendance_session_id = Column(Integer, ForeignKey("attendance_sessions.id"))
    student_id = Column(Integer, ForeignKey("users.id"))
    
    # Attendance status
    status = Column(Enum(AttendanceStatus), nullable=False)
    join_time = Column(DateTime)
    leave_time = Column(DateTime)
    total_duration_minutes = Column(Integer, default=0)
    
    # Additional information
    notes = Column(Text)
    is_excused = Column(Boolean, default=False)
    excuse_reason = Column(String(500))
    
    # System tracking
    marked_by_system = Column(Boolean, default=False)
    marked_by_admin_id = Column(Integer, ForeignKey("admins.id"))
    
    # Location data (for physical attendance)
    check_in_latitude = Column(Float)
    check_in_longitude = Column(Float)
    check_in_accuracy_meters = Column(Float)
    
    # QR code verification
    qr_code_scanned = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    attendance_session = relationship("AttendanceSession", back_populates="attendance_records")
    student = relationship("User")
    marked_by_admin = relationship("Admin")

class Reminder(Base):
    __tablename__ = "reminders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(200), nullable=False)
    message = Column(Text)
    reminder_datetime = Column(DateTime, nullable=False)
    
    # Related entities
    event_id = Column(Integer, ForeignKey("calendar_events.id"))
    assignment_id = Column(Integer, ForeignKey("assignments.id"))
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    
    # Notification preferences
    send_email = Column(Boolean, default=True)
    send_push = Column(Boolean, default=True)
    send_sms = Column(Boolean, default=False)
    
    # Status
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    event = relationship("CalendarEvent")
    assignment = relationship("Assignment")
    quiz = relationship("Quiz")

class Deadline(Base):
    __tablename__ = "deadlines"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    due_datetime = Column(DateTime, nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"))
    
    # Related entities
    assignment_id = Column(Integer, ForeignKey("assignments.id"))
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    
    # Deadline settings
    is_hard_deadline = Column(Boolean, default=True)
    late_penalty_percent = Column(Float, default=0.0)
    max_late_days = Column(Integer, default=0)
    
    # Reminder settings
    reminder_days_before = Column(String(50), default="7,3,1")  # Comma-separated days
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    course = relationship("Course")
    assignment = relationship("Assignment")
    quiz = relationship("Quiz")

class SyncSettings(Base):
    __tablename__ = "sync_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    
    # External calendar sync
    google_calendar_enabled = Column(Boolean, default=False)
    google_calendar_token = Column(Text)
    outlook_calendar_enabled = Column(Boolean, default=False)
    outlook_calendar_token = Column(Text)
    
    # Sync preferences
    sync_assignments = Column(Boolean, default=True)
    sync_quizzes = Column(Boolean, default=True)
    sync_sessions = Column(Boolean, default=True)
    sync_events = Column(Boolean, default=True)
    
    # Notification preferences
    email_notifications = Column(Boolean, default=True)
    push_notifications = Column(Boolean, default=True)
    sms_notifications = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User")