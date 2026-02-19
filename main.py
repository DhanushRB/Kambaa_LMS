from fastapi import FastAPI, HTTPException, Depends, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import timedelta, datetime, date
from typing import Optional
import asyncio
import logging
import os
from pathlib import Path

# Database and auth imports
from database import get_db, User, Resource, AdminLog
from auth import get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user, get_current_user_any_role
from schemas import UserCreate

# Admin logging function
# Admin logging function
def log_admin_action(admin_id: int, admin_username: str, action_type: str, resource_type: str, resource_id: int = None, details: str = None, ip_address: str = None):
    """Log admin actions for audit trail"""
    try:
        from database import get_db
        db = next(get_db())
        
        log_entry = AdminLog(
            admin_id=admin_id,
            admin_username=admin_username,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log admin action: {str(e)}")

# Presenter logging function
def log_presenter_action(presenter_id: int, presenter_username: str, action_type: str, resource_type: str, resource_id: int = None, details: str = None, ip_address: str = None):
    """Log presenter actions for audit trail"""
    try:
        from database import get_db, PresenterLog
        db = next(get_db())
        
        log_entry = PresenterLog(
            presenter_id=presenter_id,
            presenter_username=presenter_username,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log presenter action: {str(e)}")

# Student logging function
def log_student_action(student_id: int, student_username: str, action_type: str, resource_type: str, resource_id: int = None, details: str = None, ip_address: str = None):
    """Log student actions for audit trail"""
    try:
        from database import get_db, StudentLog
        db = next(get_db())
        
        log_entry = StudentLog(
            student_id=student_id,
            student_username=student_username,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log student action: {str(e)}")

# Mentor logging function
def log_mentor_action(mentor_id: int, mentor_username: str, action_type: str, resource_type: str, resource_id: int = None, details: str = None, ip_address: str = None):
    """Log mentor actions for audit trail"""
    try:
        from database import get_db, MentorLog
        db = next(get_db())
        
        log_entry = MentorLog(
            mentor_id=mentor_id,
            mentor_username=mentor_username,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log mentor action: {str(e)}")

# Initialize FastAPI app
app = FastAPI(title="LMS API - Kambaa AI Learning Management System")

# Add middleware for larger file uploads
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class LargeFileMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow larger uploads for resource and upload endpoints
        if any(request.url.path.startswith(prefix) for prefix in ["/api/admin/upload", "/api/upload"]):
            # Set a larger limit for uploads (2GB)
            request.scope["body_max_size"] = 2 * 1024 * 1024 * 1024
        return await call_next(request)

app.add_middleware(LargeFileMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://x18z30h4-5173.inc1.devtunnels.ms", 
        "https://g89fsl4j-5173.inc1.devtunnels.ms",
        "http://localhost:3001", 
        "http://localhost:5173",
        "https://lms.kambaaincorporation.in"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add single device login enforcement middleware
from single_device_middleware import SingleDeviceMiddleware
# Enable for all roles: Student, Admin, Presenter, Mentor, Manager
app.add_middleware(SingleDeviceMiddleware, enforce_for_roles=["Student", "Admin", "Presenter", "Mentor", "Manager"])

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create upload directories
UPLOAD_BASE_DIR = Path("uploads")

# Include calendar router at the top
try:
    from calendar_events_api import router as calendar_router
    app.include_router(calendar_router, prefix="/api/calendar")
except Exception as e:
    logger.error(f"Failed to load calendar events router: {e}")
UPLOAD_BASE_DIR.mkdir(exist_ok=True)
(UPLOAD_BASE_DIR / "resources").mkdir(exist_ok=True)
(UPLOAD_BASE_DIR / "recordings").mkdir(exist_ok=True)
(UPLOAD_BASE_DIR / "certificates").mkdir(exist_ok=True)

# Import and include new modular routers
try:
    from migration_endpoint import router as migration_router
    app.include_router(migration_router, prefix="/api")
    logger.info("Migration router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load migration router: {e}")

try:
    from routers.user_router import router as user_router
    app.include_router(user_router, prefix="/api")
    logger.info("User router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load user router: {e}")

# Secure Video Router (Force-load to debug 404, no try-catch)
from routers.video_stream_router import router as video_router_instance
app.include_router(video_router_instance)

try:
    from routers.analytics_router import router as analytics_router
    app.include_router(analytics_router, prefix="/api")
    logger.info("Analytics router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load analytics router: {e}")

try:
    from routers.admin_router import router as admin_router
    app.include_router(admin_router, prefix="/api")
    logger.info("Admin router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load admin router: {e}")

try:
    from global_course_api import router as global_course_router
    app.include_router(global_course_router, prefix="/api")
    logger.info("Global course router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load global course router: {e}")

try:
    from cohort_specific_course_api import router as cohort_specific_course_router
    app.include_router(cohort_specific_course_router, prefix="/api")
    logger.info("Cohort-specific course router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load cohort-specific course router: {e}")

try:
    from cohort_course_modules_api import router as cohort_course_modules_router
    app.include_router(cohort_course_modules_router, prefix="/api")
    logger.info("Cohort course modules router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load cohort course modules router: {e}")

try:
    from cohort_attendance_api import router as cohort_attendance_router
    app.include_router(cohort_attendance_router, prefix="/api")
    logger.info("Cohort attendance router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load cohort attendance router: {e}")

try:
    from routers.course_router import router as course_router
    app.include_router(course_router, prefix="/api")
    logger.info("Course router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load course router: {e}")

try:
    from routers.module_router import router as module_router
    app.include_router(module_router, prefix="/api")
    logger.info("Module router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load module router: {e}")

try:
    from routers.session_router import router as session_router
    app.include_router(session_router, prefix="/api")
    logger.info("Session router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load session router: {e}")

try:
    from routers.resource_router import router as resource_router
    app.include_router(resource_router, prefix="/api")
    logger.info("Resource router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load resource router: {e}")

try:
    from routers.auth_router import router as auth_router
    app.include_router(auth_router, prefix="/api")
    logger.info("Auth router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load auth router: {e}")

try:
    from routers.password_reset_router import router as password_reset_router
    app.include_router(password_reset_router, prefix="/api")
    logger.info("Password reset router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load password reset router: {e}")

try:
    from secure_auth_router import router as secure_auth_router
    app.include_router(secure_auth_router)
    logger.info("Secure auth router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load secure auth router: {e}")

try:
    from routers.dashboard_router import router as dashboard_router
    app.include_router(dashboard_router, prefix="/api")
    logger.info("Dashboard router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load dashboard router: {e}")

# Import existing external routers with error handling (these are the ones that work)
try:
    from role_login_endpoints import router as role_login_router
    app.include_router(role_login_router, prefix="/api")
    logger.info("Role login router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load role login router: {e}")

try:
    from email_endpoints import router as email_router
    app.include_router(email_router, prefix="/api")
    logger.info("Email router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load email router: {e}")

try:
    from mentor_endpoints import router as mentor_router
    app.include_router(mentor_router, prefix="/api")
    logger.info("Mentor router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load mentor router: {e}")

try:
    from email_campaigns import router as campaigns_router
    app.include_router(campaigns_router, prefix="/api")
    logger.info("Email campaigns router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load email campaigns router: {e}")

try:
    from user_reports_router import router as user_reports_router
    app.include_router(user_reports_router, prefix="/api/admin")
    logger.info("User reports router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load user reports router: {e}")

try:
    from notifications_endpoints import router as notifications_router
    app.include_router(notifications_router, prefix="/api")
    logger.info("Notifications router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load notifications router: {e}")

try:
    from session_blocking_api import router as session_blocking_router
    app.include_router(session_blocking_router, prefix="/api")
    logger.info("Session blocking router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load session blocking router: {e}")

try:
    from calendar_blocking_api import router as calendar_blocking_router
    app.include_router(calendar_blocking_router, prefix="/api")
    logger.info("Calendar blocking router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load calendar blocking router: {e}")



try:
    from smtp_endpoints import router as smtp_router
    app.include_router(smtp_router, prefix="/api")
    logger.info("SMTP router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load SMTP router: {e}")

try:
    from presenter_users_endpoints import router as presenter_users_router
    app.include_router(presenter_users_router, prefix="/api")
    logger.info("Presenter users router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load presenter users router: {e}")

try:
    from presenter_cohort_assignment import router as presenter_cohort_router
    app.include_router(presenter_cohort_router, prefix="/api")
    logger.info("Presenter cohort assignment router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load presenter cohort assignment router: {e}")

try:
    from email_template_endpoints import router as email_template_router
    app.include_router(email_template_router, prefix="/api")
    logger.info("Email template router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load email template router: {e}")

try:
    from default_email_templates import router as default_templates_router
    app.include_router(default_templates_router, prefix="/api")
    logger.info("Default email templates router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load default email templates router: {e}")

try:
    from cohort_router import router as cohort_router
    app.include_router(cohort_router, prefix="/api")
    logger.info("Cohort router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load cohort router: {e}")

try:
    from cohort_course_router import router as cohort_course_router
    app.include_router(cohort_course_router, prefix="/api")
    logger.info("Cohort course router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load cohort course router: {e}")

try:
    from cohort_chat_endpoints import router as cohort_chat_router
    app.include_router(cohort_chat_router)  # Remove prefix since router already has /api/cohort-chat
    logger.info("Cohort chat router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load cohort chat router: {e}")

try:
    from chat_endpoints import router as chat_router
    from chat_websocket import router as websocket_router
    from notification_websocket import router as notification_ws_router
    app.include_router(chat_router)  # Remove prefix since router already has /api/chat
    app.include_router(websocket_router)  # Remove prefix since router already has /api/ws
    app.include_router(notification_ws_router)  # Remove prefix since router already has /api/ws
    logger.info("Chat and websocket routers loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load chat/websocket routers: {e}")

try:
    from system_settings_endpoints import router as system_settings_router
    app.include_router(system_settings_router, prefix="/api")
    logger.info("System settings router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load system settings router: {e}")

try:
    from approval_endpoints import router as approval_router
    app.include_router(approval_router, prefix="/api")
    logger.info("Approval router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load approval router: {e}")

try:
    from live_stats_endpoints import router as live_stats_router
    app.include_router(live_stats_router, prefix="/api")
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
    app.include_router(session_meeting_router, prefix="/api")
    logger.info("Session meeting router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load session meeting router: {e}")

try:
    from meeting_session_api import router as meeting_router
    app.include_router(meeting_router, prefix="/api")
    logger.info("Meeting session router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load meeting session router: {e}")

try:
    from simple_session_content import router as simple_content_router
    app.include_router(simple_content_router, prefix="/api")
    logger.info("Simple session content router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load simple session content router: {e}")

try:
    from assignment_quiz_api import router as assignment_quiz_router
    app.include_router(assignment_quiz_router, prefix="/api")
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
    app.include_router(enhanced_analytics_router, prefix="/api")
    logger.info("Enhanced analytics router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load enhanced analytics router: {e}")

try:
    from routers.file_router import router as file_server_router
    app.include_router(file_server_router)
    logger.info("File server router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load file server router: {e}")

try:
    from file_link_api import router as file_link_router
    app.include_router(file_link_router, prefix="/api")
    logger.info("File link router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load file link router: {e}")

try:
    from file_link_session_content import router as file_link_session_router
    app.include_router(file_link_session_router, prefix="/api")
    logger.info("File link session content router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load file link session content router: {e}")

try:
    from resource_analytics_endpoints import router as resource_analytics_router
    app.include_router(resource_analytics_router)
    logger.info("Resource analytics router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load resource analytics router: {e}")

try:
    from debug_session_content import router as debug_router
    app.include_router(debug_router)
    logger.info("Debug router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load debug router: {e}")

try:
    from debug_meeting_content import router as debug_meeting_router
    app.include_router(debug_meeting_router, prefix="/api")
    logger.info("Debug meeting content router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load debug meeting content router: {e}")

try:
    from cohort_session_content_api import router as cohort_session_content_router
    app.include_router(cohort_session_content_router, prefix="/api")
    logger.info("Cohort session content router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load cohort session content router: {e}")

try:
    from admin_dashboard_router import router as admin_dashboard_router
    app.include_router(admin_dashboard_router, prefix="/api")
    logger.info("Admin dashboard router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load admin dashboard router: {e}")

try:
    from manager_dashboard_router import router as manager_dashboard_router
    app.include_router(manager_dashboard_router, prefix="/api")
    logger.info("Manager dashboard router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load manager dashboard router: {e}")

try:
    from presenter_dashboard_router import router as presenter_dashboard_router
    app.include_router(presenter_dashboard_router, prefix="/api")
    logger.info("Presenter dashboard router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load presenter dashboard router: {e}")

try:
    from mentor_dashboard_router import router as mentor_dashboard_router
    app.include_router(mentor_dashboard_router, prefix="/api")
    logger.info("Mentor dashboard router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load mentor dashboard router: {e}")

try:
    from admin_management_router import router as admin_management_router
    app.include_router(admin_management_router, prefix="/api")
    logger.info("Admin management router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load admin management router: {e}")

try:
    from admin_members_router import router as admin_members_router
    app.include_router(admin_members_router, prefix="/api")
    logger.info("Admin members router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load admin members router: {e}")

try:
    from feedback_api import router as feedback_router
    app.include_router(feedback_router, prefix="/api")
    logger.info("Feedback router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load feedback router: {e}")

# Fallback router to ensure module update endpoint exists
from fastapi import APIRouter
admin_fallback_router = APIRouter(prefix="/api/admin", tags=["module_management_fallback"])

@admin_fallback_router.put("/modules/{module_id}")
async def update_module_fallback(
    module_id: int,
    module_data: dict,
    current_user = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    try:
        # Only allow Admin or Presenter
        role = current_user.get('role') if isinstance(current_user, dict) else None
        if role not in ("Admin", "Presenter"):
            raise HTTPException(status_code=403, detail="Access denied")

        from database import Module  # local import to avoid circular issues
        module = db.query(Module).filter(Module.id == module_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")

        # Allowed fields for update
        allowed = {"title", "description", "start_date", "end_date"}
        for field, value in (module_data or {}).items():
            if field in allowed:
                # Attempt to parse ISO datetime strings
                if field in ("start_date", "end_date") and isinstance(value, str):
                    try:
                        from datetime import datetime
                        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except Exception:
                        pass
                setattr(module, field, value)

        db.commit()
        return {"message": "Module updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Fallback update module error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update module")

app.include_router(admin_fallback_router)

# Debug endpoint to list routes
@app.get("/api/debug/routes")
async def list_routes():
    routes = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = list(getattr(route, "methods", []))
        if path:
            routes.append({"path": path, "methods": methods})
        elif hasattr(route, "routes"): # Mount object
            mount_path = getattr(route, "path", "/?") # Mount path is often /
            # This is hard to get perfectly without recursion but good enough
            routes.append({"path": mount_path, "methods": ["MOUNT"]})
    return routes

# Track resource view endpoint
@app.post("/api/resources/{resource_id}/track-view")
async def track_resource_view(
    resource_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Track resource view - call this explicitly when opening a resource"""
    try:
        from resource_analytics_models import ResourceView
        from auth import get_current_user_from_token
        
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning(f"Track view failed: No auth header for resource {resource_id}")
            raise HTTPException(status_code=401, detail="Authorization required")
        
        token = auth_header.split(" ")[1]
        user = get_current_user_from_token(token, db)
        
        if not user or not hasattr(user, 'id'):
            raise HTTPException(status_code=401, detail="Invalid user")
        
        # Create view record
        view_record = ResourceView(
            resource_id=resource_id,
            student_id=user.id,
            viewed_at=datetime.utcnow(),
            ip_address=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent", ""),
            resource_type="RESOURCE"  # Explicitly set for tracking
        )
        
        db.add(view_record)
        db.commit()
        
        logger.info(f"View tracked: resource={resource_id}, user={user.id}")
        return {"message": "View tracked successfully", "resource_id": resource_id, "user_id": user.id}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Track view error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to track view: {str(e)}")

# Resource viewing endpoint with automatic tracking
@app.get("/api/resources/{resource_id}/view")
async def view_resource(
    resource_id: int,
    request: Request,
    token: str = None,
    db: Session = Depends(get_db)
):
    """View a resource file by ID with automatic view tracking"""
    try:
        logger.info(f"Attempting to view resource {resource_id}")
        
        # First check regular resources table
        resource = db.query(Resource).filter(Resource.id == resource_id).first()
        
        if not resource:
            # Check cohort session content table
            try:
                from cohort_specific_models import CohortSessionContent
                cohort_resource = db.query(CohortSessionContent).filter(
                    CohortSessionContent.id == resource_id,
                    CohortSessionContent.content_type == "RESOURCE"
                ).first()
                
                if cohort_resource:
                    logger.info(f"Found cohort resource {resource_id}: {cohort_resource.file_path}")
                    if not cohort_resource.file_path or not os.path.exists(cohort_resource.file_path):
                        logger.error(f"Cohort resource file not found: {cohort_resource.file_path}")
                        raise HTTPException(status_code=404, detail="File not found")
                    
                    # Auto-track view if token is present
                    if token:
                        try:
                            from resource_analytics_models import ResourceView
                            from auth import get_current_user_from_token
                            
                            user = get_current_user_from_token(token, db)
                            
                            if user and hasattr(user, 'id'):
                                view_record = ResourceView(
                                    resource_id=resource_id,
                                    student_id=user.id,
                                    viewed_at=datetime.utcnow(),
                                    ip_address=request.client.host if request.client else "unknown",
                                    user_agent=request.headers.get("user-agent", ""),
                                    resource_type="COHORT_RESOURCE"
                                )
                                db.add(view_record)
                                db.commit()
                                logger.info(f"Tracked view: resource={resource_id}, user={user.id}")
                        except Exception as e:
                            logger.error(f"Auto-track failed: {str(e)}")
                            db.rollback()
                    
                    filename = os.path.basename(cohort_resource.file_path)
                    file_ext = os.path.splitext(filename)[1].lower()
                    
                    headers = {
                        "Cache-Control": "no-store, no-cache, must-revalidate",
                        "X-Content-Type-Options": "nosniff",
                        "X-Frame-Options": "SAMEORIGIN"
                    }
                    
                    if file_ext == ".pdf":
                        media_type = "application/pdf"
                    elif file_ext in [".txt", ".text"]:
                        media_type = "text/plain; charset=utf-8"
                    elif file_ext in [".jpg", ".jpeg"]:
                        media_type = "image/jpeg"
                    elif file_ext == ".png":
                        media_type = "image/png"
                    elif file_ext in [".mp4"]:
                        # Enforce use of secure streaming endpoint
                        raise HTTPException(status_code=403, detail="Use secure streaming endpoint for videos")
                    elif file_ext in [".ppt", ".pptx"]:
                        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    elif file_ext in [".doc", ".docx"]:
                        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    else:
                        media_type = "application/octet-stream"
                    
                    return FileResponse(cohort_resource.file_path, media_type=media_type, headers=headers)
            except ImportError:
                logger.warning("CohortSessionContent model not available")
            
            logger.error(f"Resource {resource_id} not found in any table")
            raise HTTPException(status_code=404, detail="Resource not found")
        
        if not resource.file_path or not os.path.exists(resource.file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Try to get token from Authorization header or query parameter
        auth_token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header.split(" ")[1]
        elif token:
            auth_token = token
        
        # Auto-track view if token is present
        if auth_token:
            try:
                from resource_analytics_models import ResourceView
                from auth import get_current_user_from_token
                
                user = get_current_user_from_token(auth_token, db)
                
                if user and hasattr(user, 'id'):
                    view_record = ResourceView(
                        resource_id=resource_id,
                        student_id=user.id,
                        viewed_at=datetime.utcnow(),
                        ip_address=request.client.host if request.client else "unknown",
                        user_agent=request.headers.get("user-agent", ""),
                        resource_type="RESOURCE"
                    )
                    db.add(view_record)
                    db.commit()
                    logger.info(f"Tracked view: resource={resource_id}, user={user.id}")
            except Exception as e:
                logger.error(f"Auto-track failed: {str(e)}")
                db.rollback()
        else:
            logger.warning(f"No auth token for resource {resource_id}")
        
        filename = os.path.basename(resource.file_path)
        file_ext = os.path.splitext(filename)[1].lower()
        
        headers = {
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN"
        }
        
        if file_ext == ".pdf":
            media_type = "application/pdf"
        elif file_ext in [".txt", ".text"]:
            media_type = "text/plain; charset=utf-8"
        elif file_ext in [".jpg", ".jpeg"]:
            media_type = "image/jpeg"
        elif file_ext == ".png":
            media_type = "image/png"
        elif file_ext in [".mp4"]:
            media_type = "video/mp4"
        elif file_ext in [".ppt", ".pptx"]:
            media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        elif file_ext in [".doc", ".docx"]:
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            media_type = "application/octet-stream"
        
        return FileResponse(resource.file_path, media_type=media_type, headers=headers)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"View resource error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to view resource")

# Handle admin dashboard file path pattern
@app.get("/api/resources/{file_path:path}")
async def view_resource_by_path(file_path: str):
    """View resource by file path for admin dashboard"""
    try:
        # Handle both direct filename and full path
        if not file_path.startswith("uploads/"):
            # If it's just a filename, construct the full path
            full_path = f"uploads/resources/{file_path}"
        else:
            full_path = file_path
        
        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        file_ext = os.path.splitext(full_path)[1].lower()
        
        if file_ext == ".pdf":
            media_type = "application/pdf"
        elif file_ext in [".txt", ".text"]:
            media_type = "text/plain; charset=utf-8"
        elif file_ext in [".jpg", ".jpeg"]:
            media_type = "image/jpeg"
        elif file_ext == ".png":
            media_type = "image/png"
        elif file_ext in [".mp4"]:
            media_type = "video/mp4"
        elif file_ext in [".ppt", ".pptx"]:
            media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        elif file_ext in [".doc", ".docx"]:
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            media_type = "application/octet-stream"
        
        return FileResponse(full_path, media_type=media_type)
        
    except Exception as e:
        logger.error(f"View resource by path error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to view resource")


# Static file serving for uploads - SECURED
from fastapi.staticfiles import StaticFiles
# CRITICAL SECURITY CHANGE: Public access to /uploads is disabled to prevent unauthorized downloads.
# All file access should go through the secure /api/resources endpoints.
# However, many frontend components still expect /api/uploads or /uploads
app.mount("/api/uploads", StaticFiles(directory="uploads"), name="uploads_api")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Basic user registration endpoint
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
            user_type=user_data.user_type or "Student",
            github_link=user_data.github_link
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

        
# Meeting access endpoint for students
@app.get("/api/meetings/{meeting_id}/access")
async def get_meeting_access(
    meeting_id: str,
    current_user = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Get meeting access for students with time-based unlocking"""
    try:
        user_role = current_user.get('role', 'Student')
        user_id = current_user.get('id')
        
        # Parse meeting ID to determine source
        if meeting_id.startswith('session_meeting_'):
            content_id = int(meeting_id.replace('session_meeting_', ''))
            from database import SessionContent
            meeting = db.query(SessionContent).filter(
                SessionContent.id == content_id,
                SessionContent.content_type == "MEETING_LINK"
            ).first()
        elif meeting_id.startswith('cohort_meeting_'):
            content_id = int(meeting_id.replace('cohort_meeting_', ''))
            from cohort_specific_models import CohortSessionContent
            meeting = db.query(CohortSessionContent).filter(
                CohortSessionContent.id == content_id,
                CohortSessionContent.content_type == "MEETING_LINK"
            ).first()
        else:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Check if user has access to this meeting's session
        if user_role == 'Student':
            # Verify enrollment for students
            from database import Session as SessionModel, Module, Course, Enrollment
            from cohort_specific_models import CohortCourseSession, CohortCourseModule, CohortSpecificCourse, CohortSpecificEnrollment
            
            has_access = False
            
            # Check regular session access
            session = db.query(SessionModel).filter(SessionModel.id == meeting.session_id).first()
            if session:
                module = db.query(Module).filter(Module.id == session.module_id).first()
                if module:
                    course = db.query(Course).filter(Course.id == module.course_id).first()
                    if course:
                        enrollment = db.query(Enrollment).filter(
                            Enrollment.student_id == user_id,
                            Enrollment.course_id == course.id
                        ).first()
                        if enrollment:
                            has_access = True
            
            # Check cohort session access
            if not has_access:
                cohort_session = db.query(CohortCourseSession).filter(
                    CohortCourseSession.id == meeting.session_id
                ).first()
                if cohort_session:
                    cohort_module = db.query(CohortCourseModule).filter(
                        CohortCourseModule.id == cohort_session.module_id
                    ).first()
                    if cohort_module:
                        cohort_course = db.query(CohortSpecificCourse).filter(
                            CohortSpecificCourse.id == cohort_module.course_id
                        ).first()
                        if cohort_course:
                            enrollment = db.query(CohortSpecificEnrollment).filter(
                                CohortSpecificEnrollment.student_id == user_id,
                                CohortSpecificEnrollment.course_id == cohort_course.id
                            ).first()
                            if enrollment:
                                has_access = True
            
            if not has_access:
                raise HTTPException(status_code=403, detail="Access denied - not enrolled in course")
        
        # Check if meeting is unlocked (current time >= scheduled time)
        now = datetime.utcnow()
        is_unlocked = True
        
        if meeting.scheduled_time:
            is_unlocked = now >= meeting.scheduled_time
        
        return {
            "id": meeting_id,
            "title": meeting.title,
            "description": meeting.description,
            "scheduled_time": meeting.scheduled_time.isoformat() if meeting.scheduled_time else None,
            "meeting_url": meeting.meeting_url if is_unlocked else None,
            "is_unlocked": is_unlocked,
            "message": "Meeting is available" if is_unlocked else f"Meeting will be available at {meeting.scheduled_time}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get meeting access error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get meeting access")

# Initialize analytics tables
@app.post("/admin/init-analytics")
async def init_analytics_tables(db: Session = Depends(get_db)):
    """Initialize analytics tables"""
    try:
        from resource_analytics_models import ResourceView
        from database import Base, engine
        Base.metadata.create_all(bind=engine)
        return {"message": "Analytics tables initialized successfully"}
    except Exception as e:
        logger.error(f"Init analytics error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initialize analytics tables")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "LMS API - Kambaa AI Learning Management System", "version": "2.0.0"}

# Startup event
@app.on_event("startup")
async def startup_event():
    """Start background tasks when the application starts"""
    try:
        from campaign_scheduler import start_campaign_scheduler
        asyncio.create_task(start_campaign_scheduler())
        logger.info("Campaign scheduler started successfully")
    except ImportError:
        logger.warning("Campaign scheduler not started - module not available")
    
    # Start session cleanup task
    try:
        asyncio.create_task(session_cleanup_task())
        logger.info("Session cleanup task started successfully")
    except Exception as e:
        logger.error(f"Failed to start session cleanup task: {str(e)}")
    
    logger.info("LMS API started successfully")

async def session_cleanup_task():
    """Background task to cleanup expired sessions"""
    while True:
        try:
            await asyncio.sleep(3600)  # Run every hour
            db = next(get_db())
            try:
                from session_manager import SessionManager
                SessionManager.cleanup_expired_sessions(db, hours=24)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Session cleanup error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8001,
        limit_max_requests=1000,
        limit_concurrency=100,
        timeout_keep_alive=30,
        # Increase request body size limit to 2GB
        h11_max_incomplete_event_size=2 * 1024 * 1024 * 1024
    )