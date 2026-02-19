from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    password: str = Field(..., min_length=6)
    college: str = Field(..., min_length=2, max_length=200)
    department: str = Field(..., min_length=2, max_length=100)
    year: str = Field(..., min_length=1, max_length=10)
    user_type: str = Field(..., pattern="^(Student|Faculty)$")
    github_link: Optional[str] = None
    joining_date: Optional[str] = None
    experience: Optional[str] = None
    designation: Optional[str] = None
    specialization: Optional[str] = None
    employment_type: Optional[str] = None

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = Field(None, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    password: Optional[str] = Field(None, min_length=6)
    college: Optional[str] = Field(None, min_length=2, max_length=200)
    department: Optional[str] = Field(None, min_length=2, max_length=100)
    year: Optional[str] = Field(None, min_length=1, max_length=10)
    user_type: Optional[str] = Field(None, pattern="^(Student|Faculty)$")
    github_link: Optional[str] = None

class CourseAssignmentBase(BaseModel):
    assignment_type: str = Field(..., pattern="^(all|individual|college|cohort)$")
    user_id: Optional[int] = None
    college: Optional[str] = None
    cohort_id: Optional[int] = None
    assignment_mode: str = Field(default='free', pattern="^(free|paid)$")
    amount: float = Field(default=0.0, ge=0)

class CourseAssignmentCreate(CourseAssignmentBase):
    pass

class CourseAssignmentResponse(CourseAssignmentBase):
    id: int
    course_id: int
    assigned_at: datetime
    
    class Config:
        from_attributes = True

class CourseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, min_length=10)
    duration_weeks: Optional[int] = Field(None, ge=1, le=52)
    sessions_per_week: Optional[int] = Field(None, ge=1, le=7)
    is_active: Optional[bool] = None
    payment_type: Optional[str] = Field(None, pattern="^(free|paid)$")
    default_price: Optional[float] = Field(None, ge=0)
    banner_image: Optional[str] = None
    assignments: Optional[List[CourseAssignmentCreate]] = None

class CourseCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10)
    duration_weeks: int = Field(default=12, ge=1, le=52)
    sessions_per_week: int = Field(default=2, ge=1, le=7)
    is_active: bool = Field(default=True)
    payment_type: str = Field(default='free', pattern="^(free|paid)$")
    default_price: float = Field(default=0.0, ge=0)
    banner_image: Optional[str] = None
    assignments: List[CourseAssignmentCreate] = []

class CourseAutoSetup(BaseModel):
    course_id: int
    duration_weeks: int = Field(..., ge=1, le=52)
    sessions_per_week: int = Field(default=2, ge=1, le=7)

class AdminLogin(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

class AdminCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    password: str = Field(..., min_length=6)

class PresenterCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    password: str = Field(..., min_length=6)

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)

class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')

class VerifyOTPRequest(BaseModel):
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    otp: str = Field(..., min_length=6, max_length=6)

class ResetPasswordRequest(BaseModel):
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    otp: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=6)

class CohortCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    start_date: datetime
    end_date: datetime
    instructor_name: Optional[str] = Field(None, max_length=200)


class NotificationBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    message: str = Field(..., min_length=5)
    type: str = Field(default="info", pattern="^(info|success|warning|error)$")
    action_url: Optional[str] = Field(default=None, max_length=500)


class NotificationCreate(NotificationBase):
    user_id: int


class NotificationResponse(NotificationBase):
    id: int
    user_id: int
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MarkReadRequest(BaseModel):
    notification_id: int


class PreferenceUpdate(BaseModel):
    email_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
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
    session_number: int = Field(..., ge=1, le=10)
    session_type: str = Field(default="Live Session")
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10)
    scheduled_date: Optional[str] = Field(None, description="dd-mm-yyyy")
    scheduled_time: Optional[str] = Field(None, description="--:--")
    duration_minutes: int = Field(default=60, ge=30, le=480)
    meeting_link: Optional[str] = None
    
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
    file_url: Optional[str] = None

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
    attendance_records: List[dict]

# Forum Models
class ForumCreate(BaseModel):
    module_id: int
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10)
    is_pinned: Optional[bool] = Field(default=False)

class ForumPostCreate(BaseModel):
    forum_id: int
    content: str = Field(..., min_length=5)
    parent_post_id: Optional[int] = None

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
    content_data: Optional[str] = None
    meeting_url: Optional[str] = None
    scheduled_time: Optional[datetime] = None

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
