from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as SQLSession
from sqlalchemy import func, desc
from database import get_db, User, Resource, Module, Course, Cohort, UserCohort, Session as SessionModel
from resource_analytics_models import ResourceView
from auth import get_current_admin, get_current_presenter, get_current_mentor, get_current_admin_presenter_mentor_or_manager, get_current_user_any_role
from typing import List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import json
import os
from jose import jwt
from auth import SECRET_KEY, ALGORITHM, get_current_user_info

router = APIRouter(prefix="/api")

# Track resource view
@router.post("/resources/{resource_id}/track-view")
async def track_resource_view(
    resource_id: Any,
    request: Request,
    db: SQLSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_any_role)  # Any authenticated user including students
):
    """Track when a user views a resource - creates a new record for each view"""
    try:
        # Handle prefixed IDs
        if isinstance(resource_id, str):
            if "_" in resource_id:
                try:
                    resource_id = int(resource_id.split("_")[1])
                except (IndexError, ValueError):
                    pass
            elif resource_id.isdigit():
                resource_id = int(resource_id)

        # Check if resource exists in regular resources or cohort session content
        resource = db.query(Resource).filter(Resource.id == resource_id).first()
        resource_type = "RESOURCE"
        
        if not resource:
            # Check cohort session content OR cohort course resource
            try:
                from cohort_specific_models import CohortSessionContent, CohortCourseResource
                
                # Check CohortSessionContent (original)
                cohort_resource = db.query(CohortSessionContent).filter(
                    CohortSessionContent.id == resource_id,
                    CohortSessionContent.content_type == "RESOURCE"
                ).first()
                
                if cohort_resource:
                    resource_type = "COHORT_RESOURCE"
                else:
                    # Check CohortCourseResource (new)
                    cohort_course_resource = db.query(CohortCourseResource).filter(
                        CohortCourseResource.id == resource_id
                    ).first()
                    if cohort_course_resource:
                        resource_type = "COHORT_RESOURCE"
                    else:
                        raise HTTPException(status_code=404, detail="Resource not found")
            except ImportError:
                raise HTTPException(status_code=404, detail="Resource not found")
        
        # Get client IP and user agent
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "")
        
        # Always create a new view record for each click/view
        # This ensures proper view count tracking based on actual user interactions
        view_record = ResourceView(
            resource_id=resource_id,
            student_id=current_user["id"],
            viewed_at=datetime.utcnow(),
            ip_address=client_ip,
            user_agent=user_agent,
            resource_type=resource_type
        )
        
        db.add(view_record)
        db.commit()
        
        return {"message": "Resource view tracked successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error tracking resource view: {str(e)}")

# Track resource view endpoint (alternative endpoint)
@router.post("/resources/{resource_id}/view")
async def track_resource_view_alt(
    resource_id: Any,
    request: Request,
    db: SQLSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_any_role)
):
    """Alternative endpoint for tracking resource views"""
    return await track_resource_view(resource_id, request, db, current_user)

# Get resource analytics for admin/presenter/mentor
@router.get("/resources/{resource_id}/analytics")
async def get_resource_analytics(
    resource_id: Any,
    db: SQLSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin_presenter_mentor_or_manager)
):
    """Get analytics for a specific resource"""
    try:
        # Handle prefixed IDs
        if isinstance(resource_id, str):
            if "_" in resource_id:
                try:
                    resource_id = int(resource_id.split("_")[1])
                except (IndexError, ValueError):
                    pass
            elif resource_id.isdigit():
                resource_id = int(resource_id)

        # Check regular resources first
        resource = db.query(Resource).filter(Resource.id == resource_id).first()
        
        # If not found, check cohort session content
        if not resource:
            try:
                from cohort_specific_models import CohortSessionContent
                cohort_resource = db.query(CohortSessionContent).filter(
                    CohortSessionContent.id == resource_id,
                    CohortSessionContent.content_type == "RESOURCE"
                ).first()
                
                if cohort_resource:
                    # Create a resource-like object for cohort content
                    resource = type('Resource', (), {
                        'id': cohort_resource.id,
                        'title': cohort_resource.title,
                        'resource_type': cohort_resource.file_type or 'RESOURCE',
                        'session_id': cohort_resource.session_id,
                        'uploaded_at': cohort_resource.created_at
                    })()
            except ImportError:
                pass
        
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        # Get basic view statistics
        total_views = db.query(func.count(ResourceView.id)).filter(
            ResourceView.resource_id == resource_id
        ).scalar() or 0
        
        unique_viewers = db.query(func.count(func.distinct(ResourceView.student_id))).filter(
            ResourceView.resource_id == resource_id
        ).scalar() or 0
        
        # Get session info (handle both regular and cohort sessions)
        session = None
        course = None
        
        if resource.session_id:
            # Try regular session first
            session = db.query(SessionModel).filter(SessionModel.id == resource.session_id).first()
            
            if not session:
                # Try cohort session
                try:
                    from cohort_specific_models import CohortCourseSession, CohortSpecificCourse
                    cohort_session = db.query(CohortCourseSession).filter(
                        CohortCourseSession.id == resource.session_id
                    ).first()
                    
                    if cohort_session:
                        session = type('Session', (), {
                            'id': cohort_session.id,
                            'title': cohort_session.title,
                            'module_id': cohort_session.module_id
                        })()
                        
                        # Get cohort course info
                        from cohort_specific_models import CohortCourseModule
                        cohort_module = db.query(CohortCourseModule).filter(
                            CohortCourseModule.id == cohort_session.module_id
                        ).first()
                        
                        if cohort_module:
                            cohort_course = db.query(CohortSpecificCourse).filter(
                                CohortSpecificCourse.id == cohort_module.course_id
                            ).first()
                            
                            if cohort_course:
                                course = type('Course', (), {
                                    'id': cohort_course.id,
                                    'title': cohort_course.title
                                })()
                except ImportError:
                    pass
            
            # Handle regular session course lookup
            if session and hasattr(session, 'module_id') and session.module_id:
                module = db.query(Module).filter(Module.id == session.module_id).first()
                if module and module.course_id:
                    course = db.query(Course).filter(Course.id == module.course_id).first()
        
        # Get all students (simplified - just get all students)
        all_students = db.query(User).filter(User.user_type == "Student").all()
        
        # Get student view data
        student_views = db.query(
            User.id,
            User.username,
            User.email,
            func.count(ResourceView.id).label('view_count'),
            func.max(ResourceView.viewed_at).label('last_viewed')
        ).join(
            ResourceView, User.id == ResourceView.student_id
        ).filter(
            ResourceView.resource_id == resource_id
        ).group_by(User.id, User.username, User.email).all()
        
        # Create student analytics
        student_analytics = []
        viewed_student_ids = {sv.id for sv in student_views}
        
        # Add students who have viewed
        for student_view in student_views:
            student_analytics.append({
                "student_id": student_view.id,
                "username": student_view.username,
                "email": student_view.email,
                "view_count": student_view.view_count,
                "last_viewed": student_view.last_viewed.isoformat() if student_view.last_viewed else None,
                "has_viewed": True
            })
        
        # Add students who haven't viewed (limit to first 50 for performance)
        for student in all_students[:50]:
            if student.id not in viewed_student_ids:
                student_analytics.append({
                    "student_id": student.id,
                    "username": student.username,
                    "email": student.email,
                    "view_count": 0,
                    "last_viewed": None,
                    "has_viewed": False
                })
        
        student_analytics.sort(key=lambda x: (-x["view_count"], x["username"]))
        
        return {
            "resource": {
                "id": resource.id,
                "title": resource.title,
                "resource_type": resource.resource_type,
                "session_title": session.title if session else "Unknown Session",
                "course_title": course.title if course else "Unknown Course"
            },
            "summary": {
                "total_views": total_views,
                "unique_viewers": unique_viewers,
                "total_students": len(all_students),
                "view_percentage": round((unique_viewers / len(all_students)) * 100, 2) if all_students else 0
            },
            "student_analytics": student_analytics
        }
        
    except Exception as e:
        return {
            "resource": {
                "id": resource_id,
                "title": "Unknown Resource",
                "resource_type": "Unknown",
                "session_title": "Unknown Session",
                "course_title": "Unknown Course"
            },
            "summary": {
                "total_views": 0,
                "unique_viewers": 0,
                "total_students": 0,
                "view_percentage": 0
            },
            "student_analytics": [],
            "error": str(e)
        }

# Get session-level resource analytics
@router.get("/sessions/{session_id}/resource-analytics")
async def get_session_resource_analytics(
    session_id: int,
    db: SQLSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin_presenter_mentor_or_manager)
):
    """Get analytics for all resources in a session"""
    try:
        # Verify session exists
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get all resources in this session
        resources = db.query(Resource).filter(Resource.session_id == session_id).all()
        
        resource_analytics = []
        for resource in resources:
            # Get view stats for each resource
            total_views = db.query(func.count(ResourceView.id)).filter(
                ResourceView.resource_id == resource.id
            ).scalar()
            
            unique_viewers = db.query(func.count(func.distinct(ResourceView.student_id))).filter(
                ResourceView.resource_id == resource.id
            ).scalar()
            
            resource_analytics.append({
                "resource_id": resource.id,
                "title": resource.title,
                "resource_type": resource.resource_type,
                "total_views": total_views,
                "unique_viewers": unique_viewers,
                "uploaded_at": resource.uploaded_at.isoformat() if resource.uploaded_at else None
            })
        
        # Sort by total views (descending)
        resource_analytics.sort(key=lambda x: -x["total_views"])
        
        return {
            "session": {
                "id": session.id,
                "title": session.title
            },
            "resources": resource_analytics
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching session resource analytics: {str(e)}")

# Get top viewed resources across all sessions
@router.get("/analytics/top-resources")
async def get_top_viewed_resources(
    limit: int = 10,
    db: SQLSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin_presenter_mentor_or_manager)
):
    """Get top viewed resources across the platform"""
    try:
        top_resources = db.query(
            Resource.id,
            Resource.title,
            Resource.resource_type,
            SessionModel.title.label('session_title'),
            func.count(ResourceView.id).label('total_views'),
            func.count(func.distinct(ResourceView.student_id)).label('unique_viewers')
        ).join(
            ResourceView, Resource.id == ResourceView.resource_id
        ).join(
            SessionModel, Resource.session_id == SessionModel.id
        ).group_by(
            Resource.id, Resource.title, Resource.resource_type, SessionModel.title
        ).order_by(
            desc(func.count(ResourceView.id))
        ).limit(limit).all()
        
        return {
            "top_resources": [
                {
                    "resource_id": resource.id,
                    "title": resource.title,
                    "resource_type": resource.resource_type,
                    "session_title": resource.session_title,
                    "total_views": resource.total_views,
                    "unique_viewers": resource.unique_viewers
                }
                for resource in top_resources
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching top resources: {str(e)}")

# Get resource view trends (daily views for last 30 days)
@router.get("/resources/{resource_id}/trends")
async def get_resource_view_trends(
    resource_id: Any,
    days: int = 30,
    db: SQLSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin_presenter_mentor_or_manager)
):
    """Get daily view trends for a resource"""
    try:
        # Handle prefixed IDs
        if isinstance(resource_id, str):
            if "_" in resource_id:
                try:
                    resource_id = int(resource_id.split("_")[1])
                except (IndexError, ValueError):
                    pass
            elif resource_id.isdigit():
                resource_id = int(resource_id)

        # Verify resource exists
        # Verify resource exists (check regular resources first)
        resource = db.query(Resource).filter(Resource.id == resource_id).first()
        
        # If not found, check cohort session content
        if not resource:
            try:
                from cohort_specific_models import CohortSessionContent
                cohort_resource = db.query(CohortSessionContent).filter(
                    CohortSessionContent.id == resource_id,
                    CohortSessionContent.content_type == "RESOURCE"
                ).first()
                
                if cohort_resource:
                    # Create a resource-like object for cohort content
                    resource = type('Resource', (), {
                        'id': cohort_resource.id,
                        'title': cohort_resource.title,
                        'resource_type': cohort_resource.file_type or 'RESOURCE',
                        'session_id': cohort_resource.session_id,
                        'uploaded_at': cohort_resource.created_at
                    })()
            except ImportError:
                pass

        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        # Get date range
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days)
        
        # Get daily view counts
        daily_views = db.query(
            func.date(ResourceView.viewed_at).label('view_date'),
            func.count(ResourceView.id).label('view_count'),
            func.count(func.distinct(ResourceView.student_id)).label('unique_viewers')
        ).filter(
            ResourceView.resource_id == resource_id,
            func.date(ResourceView.viewed_at) >= start_date
        ).group_by(
            func.date(ResourceView.viewed_at)
        ).order_by(
            func.date(ResourceView.viewed_at)
        ).all()
        
        # Create complete date range with zero values for missing dates
        trends = []
        current_date = start_date
        view_data = {str(dv.view_date): {"views": dv.view_count, "unique_viewers": dv.unique_viewers} for dv in daily_views}
        
        while current_date <= end_date:
            date_str = str(current_date)
            trends.append({
                "date": date_str,
                "views": view_data.get(date_str, {"views": 0})["views"],
                "unique_viewers": view_data.get(date_str, {"unique_viewers": 0})["unique_viewers"]
            })
            current_date += timedelta(days=1)
        
        return {
            "resource": {
                "id": resource.id,
                "title": resource.title
            },
            "period": {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "days": days
            },
            "trends": trends
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching resource trends: {str(e)}")

@router.get("/resources/{resource_id}/serve")
async def serve_resource_with_tracking(
    resource_id: Any,
    request: Request,
    token: str = None,
    db: SQLSession = Depends(get_db)
):
    """Serve resource file with automatic view tracking"""
    try:
        # Handle prefixed IDs
        if isinstance(resource_id, str):
            if "_" in resource_id:
                try:
                    resource_id = int(resource_id.split("_")[1])
                except (IndexError, ValueError):
                    pass
            elif resource_id.isdigit():
                resource_id = int(resource_id)

        # Authentication and authorization
        try:
            auth_header = request.headers.get("Authorization")
            auth_token = None
            if auth_header and auth_header.startswith("Bearer "):
                auth_token = auth_header.split(" ")[1]
            elif token:
                auth_token = token
            
            if not auth_token:
                raise HTTPException(status_code=401, detail="Authentication required")
                
            payload = jwt.decode(auth_token, SECRET_KEY, algorithms=[ALGORITHM])
            current_user = get_current_user_info(payload, db)
        except Exception as auth_error:
            raise HTTPException(status_code=401, detail=f"Authentication failed: {str(auth_error)}")
        # Get resource from database (check both tables)
        resource = db.query(Resource).filter(Resource.id == resource_id).first()
        resource_type = "RESOURCE"
        file_path = None
        
        if not resource:
            # Check global session content
            from database import SessionContent
            resource = db.query(SessionContent).filter(SessionContent.id == resource_id).first()
            if resource:
                resource_type = "RESOURCE" # Or "SESSION_CONTENT" if we want to differentiate
                file_path = resource.file_path
            else:
                # Check cohort session content
                try:
                    from cohort_specific_models import CohortSessionContent
                    resource = db.query(CohortSessionContent).filter(
                        CohortSessionContent.id == resource_id,
                        CohortSessionContent.content_type == "RESOURCE"
                    ).first()
                    if resource:
                        resource_type = "COHORT_RESOURCE"
                        file_path = resource.file_path
                    else:
                        raise HTTPException(status_code=404, detail="Resource not found")
                except ImportError:
                    raise HTTPException(status_code=404, detail="Resource not found")
        else:
            file_path = resource.file_path
            
        # Track the view automatically
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "")
        
        view_record = ResourceView(
            resource_id=resource_id,
            student_id=current_user["id"],
            viewed_at=datetime.utcnow(),
            ip_address=client_ip,
            user_agent=user_agent,
            resource_type=resource_type
        )
        
        db.add(view_record)
        db.commit()
        
        # Serve the file
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Resource file not found")
        
        # Get file extension to determine content type
        file_ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path)
        
        # Set appropriate headers for different file types
        headers = {}
        media_type = None
        
        if file_ext in [".ppt", ".pptx"]:
            # For PowerPoint files, set content type to open in browser
            if file_ext == ".ppt":
                media_type = "application/vnd.ms-powerpoint"
            else:
                media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            # Set Content-Disposition to inline to open in browser instead of downloading
            headers["Content-Disposition"] = f"inline; filename={filename}"
        elif file_ext == ".pdf":
            media_type = "application/pdf"
            headers["Content-Disposition"] = f"inline; filename={filename}"
        elif file_ext in [".mp4", ".avi", ".mov", ".wmv"]:
            media_type = "video/mp4" if file_ext == ".mp4" else "video/quicktime"
            headers["Content-Disposition"] = f"inline; filename={filename}"
        elif file_ext in [".jpg", ".jpeg", ".png", ".gif"]:
            media_type = f"image/{file_ext[1:]}"
            headers["Content-Disposition"] = f"inline; filename={filename}"
        else:
            # For other files, allow download
            headers["Content-Disposition"] = f"attachment; filename={filename}"
        
        return FileResponse(
            file_path, 
            media_type=media_type,
            headers=headers
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error serving resource: {str(e)}")