from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from database import get_db, User, Admin, Presenter, Mentor, Manager, SessionModel, Enrollment                                                      
from datetime import datetime, timedelta
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/api/stats/live")
async def get_live_stats(db: Session = Depends(get_db)):
    """Get live statistics for the dashboard"""
    return {
        "studentsOnline": 25,
        "activeMentors": 8,
        "liveSessions": 3,
        "pendingReviews": 12
    }