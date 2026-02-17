import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
from typing import List, Optional
from pydantic import BaseModel, Field
from database import get_db, Session as SessionModel, Course, Module, CalendarEvent
from assignment_quiz_models import Assignment, Quiz
from auth import get_current_user, get_current_admin, get_current_admin_or_presenter, get_current_admin_presenter_mentor_or_manager, get_current_user_any_role

router = APIRouter()
logger = logging.getLogger(__name__)

# Pydantic Models
class CalendarEventCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    event_type: str = Field(default="general")
    location: Optional[str] = None
    is_all_day: bool = False
    course_id: Optional[int] = None
    reminder_minutes: int = Field(default=15, ge=0, le=10080)

class CalendarEventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    event_type: Optional[str] = None
    location: Optional[str] = None
    is_all_day: Optional[bool] = None
    reminder_minutes: Optional[int] = Field(None, ge=0, le=10080)

# Calendar Events Endpoints
@router.post("/events")
async def create_calendar_event(
    event_data: CalendarEventCreate,
    current_admin = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Create a new calendar event"""
    try:
        from sqlalchemy import text
        from database import Admin, Presenter, Mentor
        
        # Set end_datetime if not provided
        end_datetime = event_data.end_datetime
        if not end_datetime:
            if event_data.is_all_day:
                end_datetime = event_data.start_datetime.replace(hour=23, minute=59, second=59)
            else:
                end_datetime = event_data.start_datetime + timedelta(hours=1)
        
        # Determine user type and set appropriate created_by field
        created_by_admin_id = None
        created_by_presenter_id = None
        created_by_mentor_id = None
        created_by_manager_id = None
        
        # Check user type
        from database import Manager
        if db.query(Admin).filter(Admin.id == current_admin.id).first():
            created_by_admin_id = current_admin.id
        elif db.query(Presenter).filter(Presenter.id == current_admin.id).first():
            created_by_presenter_id = current_admin.id
        elif db.query(Mentor).filter(Mentor.id == current_admin.id).first():
            created_by_mentor_id = current_admin.id
        elif db.query(Manager).filter(Manager.id == current_admin.id).first():
            created_by_manager_id = current_admin.id
        
        # Insert event using raw SQL
        result = db.execute(text("""
            INSERT INTO calendar_events 
            (title, description, start_datetime, end_datetime, event_type, location, 
             is_all_day, course_id, reminder_minutes, created_by_admin_id, created_by_presenter_id, created_by_mentor_id, created_by_manager_id, created_at)
            VALUES (:title, :description, :start_datetime, :end_datetime, :event_type, 
                    :location, :is_all_day, :course_id, :reminder_minutes, :created_by_admin_id, :created_by_presenter_id, :created_by_mentor_id, :created_by_manager_id, NOW())
        """), {
            "title": event_data.title,
            "description": event_data.description,
            "start_datetime": event_data.start_datetime,
            "end_datetime": end_datetime,
            "event_type": event_data.event_type,
            "location": event_data.location,
            "is_all_day": event_data.is_all_day,
            "course_id": event_data.course_id,
            "reminder_minutes": event_data.reminder_minutes,
            "created_by_admin_id": created_by_admin_id,
            "created_by_presenter_id": created_by_presenter_id,
            "created_by_mentor_id": created_by_mentor_id,
            "created_by_manager_id": created_by_manager_id
        })
        
        db.commit()
        
        return {
            "message": "Calendar event created successfully",
            "title": event_data.title,
            "start_datetime": event_data.start_datetime
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create calendar event: {str(e)}")

@router.get("/events")
async def get_calendar_events(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    event_type: Optional[str] = Query(None),
    course_id: Optional[int] = Query(None),
    current_user_any = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Get calendar events with optional filtering - Unified comprehensive version"""
    try:
        # Use the comprehensive logic
        calendar_data = await get_comprehensive_calendar(
            start_date=start_date,
            end_date=end_date,
            current_user_any=current_user_any,
            db=db
        )
        
        items = calendar_data["calendar_items"]
        
        # Filter by event_type if provided
        if event_type:
            items = [item for item in items if item.get("event_type") == event_type or item.get("type") == event_type]
            
        # Filter by course_id if provided (though get_comprehensive_calendar already filters for students)
        if course_id:
            items = [item for item in items if item.get("course_id") == course_id]
            
        return {
            "events": items,
            "calendar_items": items,
            "total_items": len(items)
        }
    except Exception as e:
        logger.error(f"Failed to fetch calendar events: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch calendar events: {str(e)}")

@router.get("/comprehensive")
async def get_comprehensive_calendar(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user_any = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Get comprehensive calendar data including events, sessions, assignments, and quizzes"""
    try:
        from sqlalchemy import text
        from database import Enrollment, Module, SessionMeeting
        
        # Get user role and ID
        user_role = current_user_any.get("role")
        user_id = current_user_any.get("id")
        
        # Set default date range if not provided
        if not start_date:
            start_date = date.today()
        if not end_date:
            end_date = start_date + timedelta(days=30)
        
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        all_items = []
        
        # Get enrolled courses for students
        enrolled_course_ids = set()
        if user_role == "Student":
            # 1. Direct Enrollments
            enrollments = db.query(Enrollment.course_id).filter(Enrollment.student_id == user_id).all()
            enrolled_course_ids.update(e.course_id for e in enrollments)
            
            # 2. Cohort-based course assignments
            user_cohort_id = getattr(current_user_any, "cohort_id", current_user_any.get("cohort_id"))
            if user_cohort_id:
                cohort_courses = db.query(CohortCourse.course_id).filter(CohortCourse.cohort_id == user_cohort_id).all()
                enrolled_course_ids.update(cc.course_id for cc in cohort_courses)
            
            # 3. CourseAssignment linkages
            try:
                from database import CourseAssignment
                from sqlalchemy import or_, and_
                
                user_college = getattr(current_user_any, "college", current_user_any.get("college"))
                
                ca_filters = [
                    CourseAssignment.assignment_type == 'all',
                    and_(CourseAssignment.assignment_type == 'individual', CourseAssignment.user_id == user_id)
                ]
                
                if user_cohort_id:
                    ca_filters.append(and_(CourseAssignment.assignment_type == 'cohort', CourseAssignment.cohort_id == user_cohort_id))
                
                if user_college:
                    ca_filters.append(and_(CourseAssignment.assignment_type == 'college', CourseAssignment.college == user_college))
                
                ca_course_ids = db.query(CourseAssignment.course_id).filter(or_(*ca_filters)).all()
                enrolled_course_ids.update(c.course_id for c in ca_course_ids)
            except Exception as e:
                logger.error(f"Error fetching CourseAssignment course IDs: {e}")
            
            enrolled_course_ids = list(enrolled_course_ids)
        else:
            enrolled_course_ids = []
        
        # Get calendar events
        event_query = db.query(CalendarEvent).filter(
            CalendarEvent.start_datetime >= start_datetime,
            CalendarEvent.start_datetime <= end_datetime
        )
        
        # For students, only show events for their courses or public events (course_id is NULL)
        if user_role == "Student":
            from sqlalchemy import or_
            event_query = event_query.filter(
                or_(
                    CalendarEvent.course_id.in_(enrolled_course_ids),
                    CalendarEvent.course_id.is_(None)
                )
            )
            
        events_result = event_query.order_by(CalendarEvent.start_datetime).all()
        
        for event in events_result:
            all_items.append({
                "id": f"event_{event.id}",
                "title": event.title,
                "description": event.description,
                "start_datetime": event.start_datetime,
                "end_datetime": event.end_datetime,
                "type": "event",
                "event_type": event.event_type,
                "location": event.location,
                "is_all_day": event.is_all_day,
                "course_id": event.course_id,
                "color": "#3498db"  # Blue for events
            })
        
        # Get sessions
        session_query = db.query(SessionModel).join(Module)
        if user_role == "Student":
            session_query = session_query.filter(Module.course_id.in_(enrolled_course_ids))
            
        sessions = session_query.filter(
            SessionModel.scheduled_time >= start_datetime,
            SessionModel.scheduled_time <= end_datetime
        ).all()
        
        for session in sessions:
            end_time = session.scheduled_time + timedelta(minutes=session.duration_minutes or 60)
            all_items.append({
                "id": f"session_{session.id}",
                "title": f"Session: {session.title}",
                "description": session.description,
                "start_datetime": session.scheduled_time,
                "end_datetime": end_time,
                "type": "session",
                "event_type": "session",
                "location": "Online" if session.zoom_link else session.syllabus_content,
                "is_all_day": False,
                "course_id": session.module.course_id if session.module else None,
                "course_title": session.module.course.title if session.module and session.module.course else None,
                "module_title": session.module.title if session.module else None,
                "zoom_link": session.zoom_link,
                "color": "#e74c3c"  # Red for sessions
            })
        
        # Get session meetings
        meeting_query = db.query(SessionMeeting).join(SessionModel).join(Module)
        if user_role == "Student":
            meeting_query = meeting_query.filter(Module.course_id.in_(enrolled_course_ids))
            
        session_meetings = meeting_query.filter(
            SessionMeeting.meeting_datetime >= start_datetime,
            SessionMeeting.meeting_datetime <= end_datetime,
            SessionMeeting.meeting_datetime.isnot(None)
        ).all()
        
        for meeting in session_meetings:
            end_time = meeting.meeting_datetime + timedelta(minutes=meeting.duration_minutes or 60)
            all_items.append({
                "id": f"meeting_{meeting.id}",
                "title": f"Meeting: {meeting.title}",
                "description": meeting.description,
                "start_datetime": meeting.meeting_datetime,
                "end_datetime": end_time,
                "type": "meeting",
                "event_type": "meeting",
                "location": meeting.meeting_url or meeting.location,
                "is_all_day": False,
                "course_id": None,
                "session_id": meeting.session_id,
                "meeting_url": meeting.meeting_url,
                "color": "#27ae60"  # Green for meetings
            })
        
        # Get assignment deadlines
        assignment_query = db.query(Assignment, Module.course_id, Course.title).join(
            SessionModel, Assignment.session_id == SessionModel.id
        ).join(
            Module, SessionModel.module_id == Module.id
        ).outerjoin(
            Course, Module.course_id == Course.id
        )
        
        if user_role == "Student":
            assignment_query = assignment_query.filter(Module.course_id.in_(enrolled_course_ids))
            
        assignments = assignment_query.filter(
            Assignment.due_date >= start_datetime,
            Assignment.due_date <= end_datetime
        ).all()
        
        for assignment, course_id, course_title in assignments:
            all_items.append({
                "id": f"assignment_{assignment.id}",
                "title": f"Assignment Due: {assignment.title}",
                "description": assignment.description,
                "start_datetime": assignment.due_date,
                "end_datetime": assignment.due_date,
                "type": "assignment",
                "event_type": "deadline",
                "location": "Online Submission",
                "is_all_day": False,
                "course_id": course_id,
                "course_title": course_title,
                "total_marks": assignment.total_marks,
                "color": "#f39c12"  # Orange for assignments
            })
        
        # Get quiz schedules
        quiz_query = db.query(Quiz, Module.course_id, Course.title).join(
            SessionModel, Quiz.session_id == SessionModel.id
        ).join(
            Module, SessionModel.module_id == Module.id
        ).outerjoin(
            Course, Module.course_id == Course.id
        )
        
        if user_role == "Student":
            quiz_query = quiz_query.filter(Module.course_id.in_(enrolled_course_ids))
            
        quizzes = quiz_query.filter(
            Quiz.created_at >= start_datetime,
            Quiz.created_at <= end_datetime
        ).all()
        
        for quiz, course_id, course_title in quizzes:
            quiz_end = quiz.created_at + timedelta(minutes=quiz.time_limit_minutes or 60)
            all_items.append({
                "id": f"quiz_{quiz.id}",
                "title": f"Quiz: {quiz.title}",
                "description": quiz.description,
                "start_datetime": quiz.created_at,
                "end_datetime": quiz_end,
                "type": "quiz",
                "event_type": "exam",
                "location": "Online",
                "is_all_day": False,
                "course_id": course_id,
                "course_title": course_title,
                "session_id": quiz.session_id,
                "total_marks": quiz.total_marks,
                "time_limit": quiz.time_limit_minutes,
                "color": "#9b59b6"  # Purple for quizzes
            })
        
        # Sort all items by start_datetime
        all_items.sort(key=lambda x: x["start_datetime"])
        
        return {
            "calendar_items": all_items,
            "start_date": start_date,
            "end_date": end_date,
            "total_items": len(all_items)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch comprehensive calendar: {str(e)}")

@router.get("/month/{year}/{month}")
async def get_monthly_calendar(
    year: int,
    month: int,
    current_user = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Get comprehensive calendar data for a specific month"""
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
        
        # Use the comprehensive calendar endpoint
        calendar_data = await get_comprehensive_calendar(
            start_date=start_date,
            end_date=end_date,
            current_user_any=current_user,
            db=db
        )
        
        # Group items by date for easier frontend consumption
        items_by_date = {}
        for item in calendar_data["calendar_items"]:
            item_date = item["start_datetime"].date().isoformat()
            if item_date not in items_by_date:
                items_by_date[item_date] = []
            items_by_date[item_date].append(item)
        
        return {
            "year": year,
            "month": month,
            "calendar_items": calendar_data["calendar_items"],
            "items_by_date": items_by_date,
            "total_items": calendar_data["total_items"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch monthly calendar: {str(e)}")

@router.put("/calendar/events/{event_id}")
async def update_calendar_event(
    event_id: int,
    event_data: CalendarEventUpdate,
    current_admin = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Update a calendar event"""
    try:
        from sqlalchemy import text
        
        # Check if event exists
        result = db.execute(text("SELECT id FROM calendar_events WHERE id = :event_id"), 
                          {"event_id": event_id})
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Calendar event not found")
        
        # Build update query
        update_fields = []
        params = {"event_id": event_id}
        
        update_data = event_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            update_fields.append(f"{field} = :{field}")
            params[field] = value
        
        if update_fields:
            update_fields.append("updated_at = NOW()")
            query = f"UPDATE calendar_events SET {', '.join(update_fields)} WHERE id = :event_id"
            db.execute(text(query), params)
            db.commit()
        
        return {"message": "Calendar event updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update calendar event: {str(e)}")

@router.delete("/calendar/events/{event_id}")
async def delete_calendar_event(
    event_id: int,
    current_admin = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Delete a calendar event"""
    try:
        from sqlalchemy import text
        
        # Check if event exists
        result = db.execute(text("SELECT id FROM calendar_events WHERE id = :event_id"), 
                          {"event_id": event_id})
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Calendar event not found")
        
        db.execute(text("DELETE FROM calendar_events WHERE id = :event_id"), 
                  {"event_id": event_id})
        db.commit()
        
        return {"message": "Calendar event deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete calendar event: {str(e)}")

@router.delete("/calendar/events/meeting/{meeting_id}")
async def delete_calendar_event_by_meeting(
    meeting_id: int,
    current_admin = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Delete calendar event associated with a meeting"""
    try:
        from sqlalchemy import text
        
        # Find and delete calendar events that match the meeting criteria
        # This looks for events with event_type='meeting' and checks if they're auto-generated
        result = db.execute(text("""
            DELETE FROM calendar_events 
            WHERE event_type = 'meeting' 
            AND is_auto_generated = true 
            AND (title LIKE :meeting_title OR description LIKE :meeting_desc)
        """), {
            "meeting_title": f"%Meeting%{meeting_id}%",
            "meeting_desc": f"%meeting%{meeting_id}%"
        })
        
        db.commit()
        
        return {"message": "Calendar event for meeting deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete calendar event for meeting: {str(e)}")

@router.get("/upcoming")
async def get_upcoming_events(
    days: int = Query(7, ge=1, le=30),
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get upcoming events for the next N days"""
    try:
        start_date = date.today()
        end_date = start_date + timedelta(days=days)
        
        calendar_data = await get_comprehensive_calendar(
            start_date=start_date,
            end_date=end_date,
            current_user_any=current_user,
            db=db
        )
        
        # Filter to only upcoming items (from now)
        now = datetime.now()
        upcoming_items = [
            item for item in calendar_data["calendar_items"]
            if item["start_datetime"] >= now
        ]
        
        return {
            "upcoming_events": upcoming_items[:10],  # Limit to 10 most upcoming
            "days_ahead": days,
            "total_upcoming": len(upcoming_items)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch upcoming events: {str(e)}")

@router.get("/student/calendar/month/{year}/{month}")
async def get_student_monthly_calendar(
    year: int,
    month: int,
    current_user_any = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Get comprehensive calendar data for students for a specific month (legacy wrapper)"""
    return await get_monthly_calendar(year, month, current_user_any, db)

@router.get("/today")
async def get_today_events(
    current_user = Depends(get_current_user_any_role),
    db: Session = Depends(get_db)
):
    """Get today's events"""
    try:
        today = date.today()
        
        calendar_data = await get_comprehensive_calendar(
            start_date=today,
            end_date=today,
            current_user_any=current_user,
            db=db
        )
        
        return {
            "today_events": calendar_data["calendar_items"],
            "date": today,
            "total_events": len(calendar_data["calendar_items"])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch today's events: {str(e)}")
