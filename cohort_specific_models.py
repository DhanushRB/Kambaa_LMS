from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class CohortSpecificCourse(Base):
    """Courses created specifically for cohorts - separate from global courses"""
    __tablename__ = "cohort_specific_courses"
    
    id = Column(Integer, primary_key=True, index=True)
    cohort_id = Column(Integer, ForeignKey("cohorts.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    duration_weeks = Column(Integer, default=12)
    sessions_per_week = Column(Integer, default=2)
    is_active = Column(Boolean, default=True)
    banner_image = Column(String(500), nullable=True)
    created_by = Column(Integer, ForeignKey("admins.id"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    cohort = relationship("Cohort")
    creator = relationship("Admin")
    modules = relationship("CohortCourseModule", back_populates="course")
    enrollments = relationship("CohortSpecificEnrollment", back_populates="course")

class CohortSpecificEnrollment(Base):
    """Enrollment records for cohort-specific courses"""
    __tablename__ = "cohort_specific_enrollments"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("cohort_specific_courses.id"), nullable=False)
    progress = Column(Float, default=0.0)
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    student = relationship("User")
    course = relationship("CohortSpecificCourse", back_populates="enrollments")

class CohortCourseModule(Base):
    """Modules for cohort-specific courses"""
    __tablename__ = "cohort_course_modules"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("cohort_specific_courses.id"))
    week_number = Column(Integer)
    title = Column(String(200))
    description = Column(Text)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    course = relationship("CohortSpecificCourse", back_populates="modules")
    sessions = relationship("CohortCourseSession", back_populates="module")

class CohortCourseSession(Base):
    """Sessions for cohort-specific courses"""
    __tablename__ = "cohort_course_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("cohort_course_modules.id"))
    session_number = Column(Integer)
    title = Column(String(200))
    description = Column(Text)
    scheduled_time = Column(DateTime)
    duration_minutes = Column(Integer, default=120)
    zoom_link = Column(String(500))
    recording_url = Column(String(500))
    syllabus_content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    module = relationship("CohortCourseModule", back_populates="sessions")
    resources = relationship("CohortCourseResource", back_populates="session")
    contents = relationship("CohortSessionContent", back_populates="session")
    attendances = relationship("CohortAttendance", back_populates="session")

class CohortCourseResource(Base):
    """Resources for cohort-specific course sessions"""
    __tablename__ = "cohort_course_resources"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("cohort_course_sessions.id"))
    title = Column(String(200))
    resource_type = Column(String(50))  # PDF, PPT, CODE, VIDEO, OTHER
    file_path = Column(String(500))
    file_size = Column(Integer, default=0)
    description = Column(Text)
    uploaded_by = Column(Integer, ForeignKey("admins.id"))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("CohortCourseSession", back_populates="resources")
    uploader = relationship("Admin")

class CohortAttendance(Base):
    """Attendance records for cohort-specific course sessions"""
    __tablename__ = "cohort_attendances"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("cohort_course_sessions.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    attended = Column(Boolean, default=False)
    first_join_time = Column(DateTime, nullable=True)
    last_leave_time = Column(DateTime, nullable=True)
    total_duration_minutes = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    session = relationship("CohortCourseSession", back_populates="attendances")
    student = relationship("User")

class CohortSessionContent(Base):
    """Content for cohort course sessions"""
    __tablename__ = "cohort_session_contents"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("cohort_course_sessions.id"))
    content_type = Column(String(50))  # VIDEO, QUIZ, MATERIAL, MEETING_LINK, RESOURCE
    title = Column(String(200))
    description = Column(Text)
    file_path = Column(String(500))
    file_type = Column(String(50))
    file_size = Column(Integer)
    meeting_url = Column(String(500))
    scheduled_time = Column(DateTime)
    uploaded_by = Column(Integer, ForeignKey("admins.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("CohortCourseSession", back_populates="contents")
    uploader = relationship("Admin")