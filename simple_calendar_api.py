from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
from typing import Optional
from pydantic import BaseModel
from database import get_db, CalendarEvent
from auth import get_current_user

router = APIRouter()

class CalendarEventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    event_type: str = "general"
    location: Optional[str] = None

@router.post("/calendar/events")
async def create_event(
    event_data: CalendarEventCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        end_dt = event_data.end_datetime or event_data.start_datetime + timedelta(hours=1)
        
        event = CalendarEvent(
            title=event_data.title,
            description=event_data.description,
            start_datetime=event_data.start_datetime,
            end_datetime=end_dt,
            event_type=event_data.event_type,
            location=event_data.location,
            created_by_admin_id=current_user.id
        )
        
        db.add(event)
        db.commit()
        db.refresh(event)
        
        return {"message": "Event created", "event_id": event.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/calendar/month/{year}/{month}")
async def get_month_events(
    year: int,
    month: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        from calendar_events_api import get_comprehensive_calendar
        from datetime import date, timedelta
        
        # Calculate date range for the month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        # Use the comprehensive calendar logic
        result = await get_comprehensive_calendar(
            start_date=start_date,
            end_date=end_date,
            current_user_any=current_user,
            db=db
        )
        
        return {
            "year": year,
            "month": month,
            "calendar_items": result["calendar_items"],
            "total_items": result["total_items"]
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error in simple_calendar_api: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/student/calendar/month/{year}/{month}")
async def get_student_month_events(
    year: int,
    month: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return await get_month_events(year, month, current_user, db)

# Meeting integration endpoints
@router.post("/session-content/meeting")
async def create_meeting_with_calendar(
    session_id: int,
    title: str,
    description: Optional[str] = None,
    meeting_url: str = None,
    scheduled_time: Optional[datetime] = None,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        from database import SessionContent
        
        # Create session content for meeting
        meeting_content = SessionContent(
            session_id=session_id,
            content_type="MEETING_LINK",
            title=title,
            description=description,
            meeting_url=meeting_url,
            scheduled_time=scheduled_time,
            uploaded_by=current_user.id
        )
        
        db.add(meeting_content)
        db.flush()  # Get the ID
        
        # Auto-create calendar event if scheduled_time is provided
        if scheduled_time:
            calendar_event = CalendarEvent(
                title=f"Meeting: {title}",
                description=description,
                start_datetime=scheduled_time,
                end_datetime=scheduled_time + timedelta(hours=1),
                event_type="meeting",
                location=meeting_url,
                created_by_admin_id=current_user.id
            )
            
            db.add(calendar_event)
        
        db.commit()
        
        return {
            "message": "Meeting created successfully",
            "meeting_id": meeting_content.id,
            "calendar_event_created": scheduled_time is not None
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/calendar/meetings")
async def get_calendar_meetings(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Get all meeting events from calendar
        meetings = db.query(CalendarEvent).filter(
            CalendarEvent.event_type == "meeting"
        ).all()
        
        meeting_items = []
        for meeting in meetings:
            meeting_items.append({
                "id": meeting.id,
                "title": meeting.title,
                "description": meeting.description,
                "start_datetime": meeting.start_datetime,
                "end_datetime": meeting.end_datetime,
                "meeting_url": meeting.location,
                "event_type": "meeting"
            })
        
        return {"meetings": meeting_items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))