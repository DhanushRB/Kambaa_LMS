from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import Optional
from pydantic import BaseModel
from database import get_db
from auth import get_current_admin_presenter_mentor_or_manager
from calendar_blocking_service import CalendarBlockingService

router = APIRouter(prefix="/calendar-blocking", tags=["Calendar Blocking"])

class ConflictCheckRequest(BaseModel):
    start_datetime: datetime
    end_datetime: datetime
    exclude_id: Optional[int] = None

class ConflictCheckResponse(BaseModel):
    has_conflict: bool
    message: str
    conflicting_events: list = []

@router.post("/check-conflict", response_model=ConflictCheckResponse)
async def check_time_conflict(
    request: ConflictCheckRequest,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Check if a time slot has conflicts with existing bookings"""
    try:
        has_conflict = CalendarBlockingService.check_time_conflict(
            db, 
            request.start_datetime, 
            request.end_datetime, 
            request.exclude_id
        )
        
        if has_conflict:
            return ConflictCheckResponse(
                has_conflict=True,
                message=f"Time slot {request.start_datetime} - {request.end_datetime} is already blocked",
                conflicting_events=[]
            )
        else:
            return ConflictCheckResponse(
                has_conflict=False,
                message="Time slot is available"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking conflict: {str(e)}")

@router.get("/blocked-slots")
async def get_blocked_slots(
    start_date: date = Query(..., description="Start date for blocked slots"),
    end_date: date = Query(..., description="End date for blocked slots"),
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get all blocked time slots in a date range"""
    try:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        blocked_slots = CalendarBlockingService.get_blocked_slots(
            db, start_datetime, end_datetime
        )
        
        return {
            "blocked_slots": blocked_slots,
            "start_date": start_date,
            "end_date": end_date,
            "total_blocked": len(blocked_slots)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching blocked slots: {str(e)}")

@router.get("/blocked-slots/month/{year}/{month}")
async def get_monthly_blocked_slots(
    year: int,
    month: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get blocked slots for a specific month"""
    try:
        # Validate month and year
        if month < 1 or month > 12:
            raise HTTPException(status_code=400, detail="Invalid month")
        
        # Calculate date range for the month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        blocked_slots = CalendarBlockingService.get_blocked_slots(
            db, start_datetime, end_datetime
        )
        
        # Group by date for easier frontend consumption
        slots_by_date = {}
        for slot in blocked_slots:
            slot_date = slot["start_datetime"].date().isoformat()
            if slot_date not in slots_by_date:
                slots_by_date[slot_date] = []
            slots_by_date[slot_date].append(slot)
        
        return {
            "year": year,
            "month": month,
            "blocked_slots": blocked_slots,
            "slots_by_date": slots_by_date,
            "total_blocked": len(blocked_slots)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching monthly blocked slots: {str(e)}")

@router.get("/availability/check")
async def check_availability(
    start_datetime: datetime = Query(..., description="Start datetime to check"),
    duration_minutes: int = Query(60, description="Duration in minutes"),
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Check if a specific time slot is available"""
    try:
        end_datetime = start_datetime + timedelta(minutes=duration_minutes)
        
        has_conflict = CalendarBlockingService.check_time_conflict(
            db, start_datetime, end_datetime
        )
        
        return {
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "duration_minutes": duration_minutes,
            "is_available": not has_conflict,
            "message": "Time slot is available" if not has_conflict else "Time slot is blocked"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking availability: {str(e)}")

@router.get("/next-available")
async def get_next_available_slot(
    preferred_start: datetime = Query(..., description="Preferred start datetime"),
    duration_minutes: int = Query(60, description="Duration in minutes"),
    search_days: int = Query(7, description="Number of days to search ahead"),
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Find the next available time slot after a preferred time"""
    try:
        search_end = preferred_start + timedelta(days=search_days)
        current_time = preferred_start
        
        # Search in 30-minute increments
        while current_time < search_end:
            end_time = current_time + timedelta(minutes=duration_minutes)
            
            if not CalendarBlockingService.check_time_conflict(db, current_time, end_time):
                return {
                    "available_slot": {
                        "start_datetime": current_time,
                        "end_datetime": end_time,
                        "duration_minutes": duration_minutes
                    },
                    "preferred_start": preferred_start,
                    "delay_minutes": int((current_time - preferred_start).total_seconds() / 60)
                }
            
            current_time += timedelta(minutes=30)
        
        return {
            "available_slot": None,
            "preferred_start": preferred_start,
            "message": f"No available slot found in the next {search_days} days"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding next available slot: {str(e)}")