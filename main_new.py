from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from typing import Optional
import asyncio
import logging
import os
from pathlib import Path

# Database and auth imports
from database import get_db, User
from auth import get_password_hash, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
from schemas import UserCreate

# Initialize FastAPI app
app = FastAPI(title="LMS API - Kambaa AI Learning Management System")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://x18z30h4-5173.inc1.devtunnels.ms", 
        "http://localhost:3001", 
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create upload directories
UPLOAD_BASE_DIR = Path("uploads")
UPLOAD_BASE_DIR.mkdir(exist_ok=True)
(UPLOAD_BASE_DIR / "resources").mkdir(exist_ok=True)
(UPLOAD_BASE_DIR / "recordings").mkdir(exist_ok=True)
(UPLOAD_BASE_DIR / "certificates").mkdir(exist_ok=True)

# Import and include new modular routers
try:
    from routers.auth_router import router as auth_router
    app.include_router(auth_router)
    logger.info("Auth router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load auth router: {e}")

try:
    from routers.user_router import router as user_router
    app.include_router(user_router)
    logger.info("User router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load user router: {e}")

try:
    from routers.course_router import router as course_router
    app.include_router(course_router)
    logger.info("Course router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load course router: {e}")

try:
    from routers.file_router import router as file_router
    app.include_router(file_router)
    logger.info("File router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load file router: {e}")

try:
    from routers.dashboard_router import router as dashboard_router
    app.include_router(dashboard_router)
    logger.info("Dashboard router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load dashboard router: {e}")

try:
    from routers.session_router import router as session_router
    app.include_router(session_router)
    logger.info("Session router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load session router: {e}")

try:
    from routers.admin_router import router as admin_router
    app.include_router(admin_router)
    logger.info("Admin router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load admin router: {e}")

try:
    from routers.student_router import router as student_router
    app.include_router(student_router)
    logger.info("Student router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load student router: {e}")

try:
    from routers.bulk_router import router as bulk_router
    app.include_router(bulk_router)
    logger.info("Bulk router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load bulk router: {e}")

try:
    from routers.cohort_simple_router import router as cohort_simple_router
    app.include_router(cohort_simple_router)
    logger.info("Cohort simple router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load cohort simple router: {e}")

try:
    from routers.module_router import router as module_router
    app.include_router(module_router)
    logger.info("Module router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load module router: {e}")

try:
    from routers.quiz_router import router as quiz_router
    app.include_router(quiz_router)
    logger.info("Quiz router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load quiz router: {e}")

try:
    from routers.resource_router import router as resource_router
    app.include_router(resource_router)
    logger.info("Resource router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load resource router: {e}")

try:
    from routers.analytics_router import router as analytics_router
    app.include_router(analytics_router)
    logger.info("Analytics router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load analytics router: {e}")

# Import and include existing external routers with error handling
try:
    from role_login_endpoints import router as role_login_router
    app.include_router(role_login_router)
    logger.info("Role login router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load role login router: {e}")

try:
    from email_endpoints_new import router as email_router
    app.include_router(email_router)
    logger.info("Email router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load email router: {e}")

try:
    from mentor_endpoints import router as mentor_router
    app.include_router(mentor_router)
    logger.info("Mentor router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load mentor router: {e}")

try:
    from email_campaigns import router as campaigns_router
    app.include_router(campaigns_router)
    logger.info("Email campaigns router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load email campaigns router: {e}")

try:
    from notifications_endpoints import router as notifications_router
    app.include_router(notifications_router)
    logger.info("Notifications router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load notifications router: {e}")

try:
    from calendar_events_api import router as calendar_router
    app.include_router(calendar_router)
    logger.info("Calendar events router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load calendar events router: {e}")

try:
    from smtp_endpoints import router as smtp_router
    app.include_router(smtp_router)
    logger.info("SMTP router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load SMTP router: {e}")

try:
    from presenter_users_endpoints import router as presenter_users_router
    app.include_router(presenter_users_router)
    logger.info("Presenter users router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load presenter users router: {e}")

try:
    from presenter_cohort_assignment import router as presenter_cohort_router
    app.include_router(presenter_cohort_router)
    logger.info("Presenter cohort assignment router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load presenter cohort assignment router: {e}")

try:
    from email_template_endpoints import router as email_template_router
    app.include_router(email_template_router)
    logger.info("Email template router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load email template router: {e}")

try:
    from default_email_templates import router as default_templates_router
    app.include_router(default_templates_router)
    logger.info("Default email templates router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load default email templates router: {e}")

try:
    from cohort_router import router as cohort_router
    app.include_router(cohort_router)
    logger.info("Cohort router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load cohort router: {e}")

try:
    from cohort_chat_endpoints import router as cohort_chat_router
    app.include_router(cohort_chat_router)
    logger.info("Cohort chat router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load cohort chat router: {e}")

try:
    from chat_endpoints import router as chat_router
    from chat_websocket import router as websocket_router
    from notification_websocket import router as notification_ws_router
    app.include_router(chat_router)
    app.include_router(websocket_router)
    app.include_router(notification_ws_router)
    logger.info("Chat and websocket routers loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load chat/websocket routers: {e}")

try:
    from system_settings_endpoints import router as system_settings_router
    app.include_router(system_settings_router)
    logger.info("System settings router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load system settings router: {e}")

try:
    from approval_endpoints import router as approval_router
    app.include_router(approval_router)
    logger.info("Approval router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load approval router: {e}")

try:
    from live_stats_endpoints import router as live_stats_router
    app.include_router(live_stats_router)
    logger.info("Live stats router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load live stats router: {e}")

try:
    from enhanced_session_content_api import router as enhanced_content_router
    app.include_router(enhanced_content_router)
    logger.info("Enhanced session content router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load enhanced session content router: {e}")

try:
    from session_meeting_api import router as session_meeting_router
    app.include_router(session_meeting_router)
    logger.info("Session meeting router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load session meeting router: {e}")

try:
    from meeting_session_api import router as meeting_router
    app.include_router(meeting_router)
    logger.info("Meeting session router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load meeting session router: {e}")

try:
    from simple_session_content import router as simple_content_router
    app.include_router(simple_content_router)
    logger.info("Simple session content router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load simple session content router: {e}")

try:
    from assignment_quiz_api import router as assignment_quiz_router
    app.include_router(assignment_quiz_router)
    logger.info("Assignment quiz router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load assignment quiz router: {e}")

try:
    from student_dashboard_endpoints import router as student_dashboard_router
    app.include_router(student_dashboard_router)
    logger.info("Student dashboard router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load student dashboard router: {e}")

try:
    from enhanced_analytics_endpoints import router as enhanced_analytics_router
    app.include_router(enhanced_analytics_router)
    logger.info("Enhanced analytics router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load enhanced analytics router: {e}")

try:
    from file_link_api import router as file_link_router
    app.include_router(file_link_router)
    logger.info("File link router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load file link router: {e}")

try:
    from resource_analytics_endpoints import router as resource_analytics_router
    app.include_router(resource_analytics_router)
    logger.info("Resource analytics router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load resource analytics router: {e}")

# Helper functions that are used across the application
def requires_approval(user_role: str, operation_type: str) -> bool:
    """Check if an operation requires approval based on user role"""
    restricted_roles = ['Student', 'Presenter', 'Mentor']
    major_operations = ['delete', 'unpublish', 'disable', 'archive', 'bulk_update', 'final_modification']
    
    return user_role in restricted_roles and operation_type in major_operations

def create_approval_request(db: Session, user_id: int, user_role: str, operation_type: str, 
                          target_entity_type: str, target_entity_id: int, 
                          operation_data: dict, reason: str = ""):
    """Create an approval request for restricted operations"""
    try:
        from approval_models import ApprovalRequest, EntityStatus, ApprovalStatus, OperationType
        import json
        
        # Create approval request
        approval_request = ApprovalRequest(
            requester_id=user_id,
            operation_type=OperationType(operation_type),
            target_entity_type=target_entity_type,
            target_entity_id=target_entity_id,
            operation_data=json.dumps(operation_data),
            reason=reason,
            status=ApprovalStatus.PENDING
        )
        
        db.add(approval_request)
        db.commit()
        db.refresh(approval_request)
        
        # Update entity status to pending approval
        entity_status = db.query(EntityStatus).filter(
            EntityStatus.entity_type == target_entity_type,
            EntityStatus.entity_id == target_entity_id
        ).first()
        
        if entity_status:
            entity_status.status = "pending_approval"
            entity_status.approval_request_id = approval_request.id
        else:
            entity_status = EntityStatus(
                entity_type=target_entity_type,
                entity_id=target_entity_id,
                status="pending_approval",
                approval_request_id=approval_request.id
            )
            db.add(entity_status)
        
        db.commit()
        
        return approval_request.id
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create approval request: {str(e)}")
        raise e

def format_meeting_url(url: str) -> str:
    """Ensure meeting URL has proper protocol for opening in browser"""
    if not url:
        return url
    
    url = url.strip()
    if not url:
        return url
    
    # If URL already has protocol, return as is
    if url.startswith(('http://', 'https://')):
        return url
    
    # Add https:// as default protocol
    return f"https://{url}"

def filter_meeting_links_for_student(session_contents):
    """Add meeting status and remaining time instead of filtering out"""
    processed_contents = []
    current_time = datetime.now()
    
    for content in session_contents:
        # Always include the content
        processed_content = content.copy()
        
        # For meeting links, add status and remaining time
        if content.get('content_type') == 'MEETING_LINK':
            scheduled_time = content.get('scheduled_time')
            
            if scheduled_time is None:
                # No scheduled time means it's always available
                processed_content['meeting_status'] = 'available'
                processed_content['is_locked'] = False
                processed_content['remaining_time'] = None
            else:
                # Parse scheduled time and calculate status
                try:
                    if isinstance(scheduled_time, str):
                        # Handle ISO format with timezone
                        scheduled_dt = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                        # Convert to naive datetime for comparison
                        if scheduled_dt.tzinfo is not None:
                            scheduled_dt = scheduled_dt.replace(tzinfo=None)
                    else:
                        scheduled_dt = scheduled_time
                    
                    # Compare times - if current time is BEFORE scheduled time, lock it
                    if current_time < scheduled_dt:
                        # Meeting is in future - locked with countdown
                        time_diff = scheduled_dt - current_time
                        processed_content['meeting_status'] = 'locked'
                        processed_content['is_locked'] = True
                        processed_content['remaining_time'] = int(time_diff.total_seconds())
                    else:
                        # Meeting time has passed - available
                        processed_content['meeting_status'] = 'available'
                        processed_content['is_locked'] = False
                        processed_content['remaining_time'] = None
                        
                except (ValueError, TypeError) as e:
                    # If we can't parse the time, make it available
                    processed_content['meeting_status'] = 'available'
                    processed_content['is_locked'] = False
                    processed_content['remaining_time'] = None
                    logger.error(f"Error parsing time: {e} - setting as available")
        else:
            # Non-meeting content is always available
            processed_content['meeting_status'] = None
            processed_content['is_locked'] = False
            processed_content['remaining_time'] = None
        
        processed_contents.append(processed_content)
    
    return processed_contents

# Logging functions
def log_admin_action(admin_id: int, admin_username: str, action_type: str, resource_type: str, 
                    details: str, resource_id: Optional[int] = None, ip_address: Optional[str] = None):
    """Log admin actions to database"""
    try:
        from database import SessionLocal, AdminLog
        db = SessionLocal()
        
        admin_log = AdminLog(
            admin_id=admin_id,
            admin_username=admin_username,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.add(admin_log)
        db.commit()
        db.close()
        
        logger.info(f"Admin Action Logged: {admin_username} {action_type} {resource_type}")
    except Exception as e:
        logger.error(f"Failed to log admin action: {str(e)}")

def log_presenter_action(presenter_id: int, presenter_username: str, action_type: str, resource_type: str,
                        details: str, resource_id: Optional[int] = None, ip_address: Optional[str] = None):
    """Log presenter actions to database"""
    try:
        from database import SessionLocal, PresenterLog
        db = SessionLocal()
        
        presenter_log = PresenterLog(
            presenter_id=presenter_id,
            presenter_username=presenter_username,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.add(presenter_log)
        db.commit()
        db.close()
        
        logger.info(f"Presenter Action Logged: {presenter_username} {action_type} {resource_type}")
    except Exception as e:
        logger.error(f"Failed to log presenter action: {str(e)}")

def log_student_action(student_id: int, student_username: str, action_type: str, resource_type: str,
                      details: str, resource_id: Optional[int] = None, ip_address: Optional[str] = None):
    """Log student actions to database"""
    try:
        from database import SessionLocal, StudentLog
        db = SessionLocal()
        
        student_log = StudentLog(
            student_id=student_id,
            student_username=student_username,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.add(student_log)
        db.commit()
        db.close()
        
        logger.info(f"Student Action Logged: {student_username} {action_type} {resource_type}")
    except Exception as e:
        logger.error(f"Failed to log student action: {str(e)}")

def log_mentor_action(mentor_id: int, mentor_username: str, action_type: str, resource_type: str,
                     details: str, resource_id: Optional[int] = None, ip_address: Optional[str] = None):
    """Log mentor actions to database"""
    try:
        from database import SessionLocal, MentorLog
        db = SessionLocal()
        
        mentor_log = MentorLog(
            mentor_id=mentor_id,
            mentor_username=mentor_username,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.add(mentor_log)
        db.commit()
        db.close()
        
        logger.info(f"Mentor Action Logged: {mentor_username} {action_type} {resource_type}")
    except Exception as e:
        logger.error(f"Failed to log mentor action: {str(e)}")

# Basic user registration endpoint (kept in main for backward compatibility)
@app.post("/auth/register")
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """User registration endpoint"""
    try:
        if db.query(User).filter(User.username == user_data.username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        if db.query(User).filter(User.email == user_data.email).first():
            raise HTTPException(status_code=400, detail="Email already exists")
        
        hashed_password = get_password_hash(user_data.password)
        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed_password,
            role=user_data.user_type or "Student",
            college=user_data.college,
            department=user_data.department,
            year=user_data.year,
            user_type=user_data.user_type or "Student"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return {"message": "User registered successfully", "user_id": user.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now()}

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "LMS API - Kambaa AI Learning Management System", "version": "2.0.0"}

# Startup event to start background services
@app.on_event("startup")
async def startup_event():
    """Start background tasks when the application starts"""
    try:
        from campaign_scheduler import start_campaign_scheduler
        # Start campaign scheduler in background
        asyncio.create_task(start_campaign_scheduler())
        logger.info("Campaign scheduler started successfully")
    except ImportError:
        logger.warning("Campaign scheduler not started - module not available")
    
    logger.info("LMS API started successfully with modular architecture")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)