from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from database import get_db, User, Resource, Session as SessionModel, Module, Course, Cohort, UserCohort
from resource_analytics_models import ResourceView
from auth import get_current_admin_presenter_mentor_or_manager
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json

router = APIRouter(prefix="/api")

@router.get("/analytics/overview")
async def get_analytics_overview(
    days: int = Query(30, description="Number of days to look back"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin_presenter_mentor_or_manager)
):
    """Get platform-wide analytics overview"""
    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Total resources
        total_resources = db.query(func.count(Resource.id)).scalar()
        
        # Total views in time period
        total_views = db.query(func.count(ResourceView.id)).filter(
            ResourceView.viewed_at >= start_date
        ).scalar()
        
        # Active students (students who viewed at least one resource in time period)
        active_students = db.query(func.count(func.distinct(ResourceView.student_id))).filter(
            ResourceView.viewed_at >= start_date
        ).scalar()
        
        # Total students in system
        total_students = db.query(func.count(User.id)).filter(
            User.user_type == "Student"
        ).scalar()
        
        # Calculate average engagement
        avg_engagement = 0
        if total_students > 0:
            avg_engagement = round((active_students / total_students) * 100, 2)
        
        return {
            "period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "total_resources": total_resources,
            "total_views": total_views,
            "active_students": active_students,
            "total_students": total_students,
            "avg_engagement": avg_engagement
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching overview analytics: {str(e)}")

@router.get("/analytics/top-resources")
async def get_top_resources(
    limit: int = Query(10),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin_presenter_mentor_or_manager)
):
    """Get top viewed resources"""
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