from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime

# Authentication Models
class UserLogin(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    role: str = Field(..., pattern="^(Student)$")

class AdminLogin(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

# User Management Models
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    password: str = Field(..., min_length=6)
    college: str = Field(..., min_length=2, max_length=200)
    department: str = Field(..., min_length=2, max_length=100)
    year: str = Field(..., min_length=4, max_length=10)
    user_type: str = Field(default="Student", pattern="^(Student|Faculty)$")
    role: Optional[str] = Field(default="Student", pattern="^(Student|Faculty)$")
    
    # Faculty-specific fields (optional for students)
    experience: Optional[int] = Field(None, ge=0, le=50)
    designation: Optional[str] = Field(None, max_length=200)
    specialization: Optional[str] = Field(None, max_length=500)
    employment_type: Optional[str] = Field("Full-time", pattern="^(Full-time|Visiting|Contract|Part-time)$")
    joining_date: Optional[str] = None  # Will be converted to datetime
    
    @validator('experience', pre=True, always=True)
    def validate_experience(cls, v, values):
        user_type = values.get('user_type', 'Student')
        if user_type == 'Faculty':
            if v is None or v == '' or v == 0:
                raise ValueError('Experience is required for faculty and must be greater than 0')
            try:
                return int(v)
            except (ValueError, TypeError):
                raise ValueError('Experience must be a valid number')
        return v
    
    @validator('designation', pre=True, always=True)
    def validate_designation(cls, v, values):
        user_type = values.get('user_type', 'Student')
        if user_type == 'Faculty' and (not v or v.strip() == ''):
            raise ValueError('Designation is required for faculty')
        return v.strip() if v else v
    
    @validator('specialization', pre=True, always=True)
    def validate_specialization(cls, v, values):
        user_type = values.get('user_type', 'Student')
        if user_type == 'Faculty' and (not v or v.strip() == ''):
            raise ValueError('Specialization is required for faculty')
        return v.strip() if v else v

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = Field(None, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    password: Optional[str] = Field(None, min_length=6)
    college: Optional[str] = Field(None, min_length=2, max_length=200)
    department: Optional[str] = Field(None, min_length=2, max_length=100)
    year: Optional[str] = Field(None, min_length=4, max_length=10)
    user_type: Optional[str] = Field(None, pattern="^(Student|Faculty)$")
    role: Optional[str] = Field(None, pattern="^(Student|Faculty)$")
    
    # Faculty-specific fields
    experience: Optional[int] = Field(None, ge=0, le=50)
    designation: Optional[str] = Field(None, max_length=200)
    specialization: Optional[str] = Field(None, max_length=500)
    employment_type: Optional[str] = Field(None, pattern="^(Full-time|Visiting|Contract|Part-time)$")
    joining_date: Optional[str] = None

# Course Management Models
class CourseAutoSetup(BaseModel):
    course_id: int
    duration_weeks: int = Field(..., ge=1, le=52)
    sessions_per_week: int = Field(default=2, ge=1, le=7)

# Module Management Models
class ModuleCreate(BaseModel):
    course_id: int
    week_number: int = Field(..., ge=1, le=52)
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class ModuleUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, min_length=10)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

# Session Management Models
class SessionCreate(BaseModel):
    module_id: int
    session_number: int = Field(..., ge=1, le=10, description="Enter session number (1-10)")
    session_type: str = Field(default="Live Session", description="Session type")
    title: str = Field(..., min_length=5, max_length=200, description="Enter session title (minimum 5 characters)")
    description: str = Field(..., min_length=10, description="Enter session description (minimum 10 characters)")
    scheduled_date: Optional[str] = Field(None, description="dd-mm-yyyy")
    scheduled_time: Optional[str] = Field(None, description="--:--")
    duration_minutes: int = Field(default=60, ge=30, le=480, description="Duration (Minutes)")
    meeting_link: Optional[str] = Field(None, description="Meeting Link (Optional)")
    
    @validator('scheduled_date', pre=True)
    def validate_scheduled_date(cls, v):
        if v and v.strip():
            try:
                datetime.strptime(v, '%d-%m-%Y')
                return v
            except ValueError:
                raise ValueError('Date must be in dd-mm-yyyy format')
        return v
    
    @validator('scheduled_time', pre=True)
    def validate_scheduled_time(cls, v):
        if v and v.strip():
            try:
                datetime.strptime(v, '%H:%M')
                return v
            except ValueError:
                raise ValueError('Time must be in HH:MM format')
        return v

class SessionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, min_length=10)
    scheduled_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=30, le=480)
    zoom_link: Optional[str] = None
    recording_url: Optional[str] = None
    syllabus_content: Optional[str] = None

# Resource Management Models
class ResourceCreate(BaseModel):
    session_id: int
    title: str = Field(..., min_length=3, max_length=200)
    resource_type: str = Field(..., pattern="^(PDF|PPT|VIDEO|CODE|OTHER|TXT|FILE_LINK)$")
    file_path: str
    file_size: Optional[int] = Field(default=0, ge=0)
    description: Optional[str] = None
    file_url: Optional[str] = None  # For FILE_LINK type

# Attendance Models
class AttendanceCreate(BaseModel):
    session_id: int
    student_id: int
    attended: bool
    duration_minutes: Optional[int] = Field(default=0, ge=0)
    join_time: Optional[datetime] = None
    leave_time: Optional[datetime] = None

class AttendanceBulkCreate(BaseModel):
    session_id: int
    attendance_records: List[dict]  # [{"student_id": 1, "attended": true, "duration_minutes": 120}]

# Quiz Models
class QuizCreate(BaseModel):
    session_id: int
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    total_marks: int = Field(..., ge=1, le=1000)
    time_limit_minutes: Optional[int] = Field(default=60, ge=5, le=300)
    questions: Optional[str] = None  # JSON string containing questions
    is_active: Optional[bool] = Field(default=True)

class AIQuizGenerateRequest(BaseModel):
    session_id: int
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    question_type: str
    num_questions: int = Field(..., ge=1, le=50)
    
    @validator('question_type')
    def validate_question_type(cls, v):
        if isinstance(v, str):
            v = v.upper()
        valid_types = ['MCQ', 'TRUE_FALSE', 'SHORT_ANSWER']
        if v not in valid_types:
            raise ValueError(f'question_type must be one of {valid_types}')
        return v
    
    @validator('num_questions', pre=True)
    def validate_num_questions(cls, v):
        if isinstance(v, str):
            try:
                v = int(v)
            except ValueError:
                raise ValueError('num_questions must be a valid integer')
        return v
    
    class Config:
        extra = "ignore"

class QuizFileProcessRequest(BaseModel):
    session_id: int
    file_content: str

class QuizAttemptCreate(BaseModel):
    quiz_id: int
    score: float = Field(..., ge=0)
    answers: Optional[str] = None  # JSON string containing answers
    time_taken_minutes: Optional[int] = Field(default=0, ge=0)

# Forum Models
class ForumCreate(BaseModel):
    module_id: int
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10)
    is_pinned: Optional[bool] = Field(default=False)

class ForumPostCreate(BaseModel):
    forum_id: int
    content: str = Field(..., min_length=5)
    parent_post_id: Optional[int] = None  # For replies

# Session Content Models
class SessionContentCreate(BaseModel):
    session_id: int
    content_type: str = Field(..., pattern="^(VIDEO|QUIZ|MATERIAL|RESOURCE|LIVE_SESSION|MEETING_LINK)$")
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = Field(default=0, ge=0)
    duration_minutes: Optional[int] = Field(default=60, ge=0)
    content_data: Optional[str] = None  # JSON data for quizzes, live session links, etc.
    meeting_url: Optional[str] = None  # For meeting links
    scheduled_time: Optional[datetime] = None  # For meeting links

# Certificate Models
class CertificateGenerate(BaseModel):
    student_id: int
    course_id: int
    completion_date: Optional[datetime] = None

# Progress Models
class ProgressUpdate(BaseModel):
    student_id: int
    course_id: int
    progress_percentage: float = Field(..., ge=0, le=100)

# Notification Models
class NotificationCreate(BaseModel):
    user_id: Optional[int] = None
    title: str = Field(..., min_length=3, max_length=200)
    message: str = Field(..., min_length=5)
    notification_type: str = Field(default="INFO")  # INFO, WARNING, SUCCESS, ERROR
    is_global: Optional[bool] = Field(default=False)