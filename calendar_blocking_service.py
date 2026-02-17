from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from database import CalendarEvent, Session as SessionModel, SessionMeeting
from typing import List, Optional

class CalendarBlockingService:
    """Service to handle calendar blocking for sessions and meetings"""
    
    @staticmethod
    def check_time_conflict(db: Session, start_time: datetime, end_time: datetime, exclude_id: Optional[int] = None) -> bool:
        """Check if there's a time conflict with existing events/sessions/meetings"""
        
        # Check calendar events
        calendar_conflicts = db.query(CalendarEvent).filter(
            and_(
                CalendarEvent.id != exclude_id if exclude_id else True,
                or_(
                    # New event starts during existing event
                    and_(CalendarEvent.start_datetime <= start_time, CalendarEvent.end_datetime > start_time),
                    # New event ends during existing event
                    and_(CalendarEvent.start_datetime < end_time, CalendarEvent.end_datetime >= end_time),
                    # New event completely contains existing event
                    and_(CalendarEvent.start_datetime >= start_time, CalendarEvent.end_datetime <= end_time)
                )
            )
        ).first()
        
        if calendar_conflicts:
            return True
            
        # Check sessions
        session_conflicts = db.query(SessionModel).filter(
            SessionModel.scheduled_time.isnot(None),
            or_(
                # Session starts during new event
                and_(SessionModel.scheduled_time >= start_time, SessionModel.scheduled_time < end_time),
                # Session ends during new event (assuming 2 hour default duration)
                and_(
                    SessionModel.scheduled_time < start_time,
                    SessionModel.scheduled_time + timedelta(minutes=SessionModel.duration_minutes or 120) > start_time
                )
            )
        ).first()
        
        if session_conflicts:
            return True
            
        # Check session meetings
        meeting_conflicts = db.query(SessionMeeting).filter(
            SessionMeeting.meeting_datetime.isnot(None),
            or_(
                # Meeting starts during new event
                and_(SessionMeeting.meeting_datetime >= start_time, SessionMeeting.meeting_datetime < end_time),
                # Meeting ends during new event
                and_(
                    SessionMeeting.meeting_datetime < start_time,
                    SessionMeeting.meeting_datetime + timedelta(minutes=SessionMeeting.duration_minutes or 60) > start_time
                )
            )
        ).first()
        
        return meeting_conflicts is not None
    
    @staticmethod
    def create_session_block(db: Session, session: SessionModel, created_by_id: int, user_type: str) -> Optional[int]:
        """Automatically create calendar block when session is scheduled"""
        if not session.scheduled_time:
            return None
            
        end_time = session.scheduled_time + timedelta(minutes=session.duration_minutes or 120)
        
        # Check for conflicts
        if CalendarBlockingService.check_time_conflict(db, session.scheduled_time, end_time):
            raise ValueError(f"Time slot conflict: {session.scheduled_time} - {end_time}")
        
        # Create calendar event
        calendar_event = CalendarEvent(
            title=f"Session: {session.title}",
            description=f"Blocked for session: {session.description or session.title}",
            start_datetime=session.scheduled_time,
            end_datetime=end_time,
            event_type="session_block",
            is_auto_generated=True,
            created_by_admin_id=created_by_id if user_type == "Admin" else None,
            created_by_presenter_id=created_by_id if user_type == "Presenter" else None,
            created_by_mentor_id=created_by_id if user_type == "Mentor" else None
        )
        
        db.add(calendar_event)
        db.commit()
        db.refresh(calendar_event)
        
        return calendar_event.id
    
    @staticmethod
    def create_meeting_block(db: Session, meeting: SessionMeeting, created_by_id: int, user_type: str) -> Optional[int]:
        """Automatically create calendar block when meeting is scheduled"""
        if not meeting.meeting_datetime:
            return None
            
        end_time = meeting.meeting_datetime + timedelta(minutes=meeting.duration_minutes or 60)
        
        # Check for conflicts
        if CalendarBlockingService.check_time_conflict(db, meeting.meeting_datetime, end_time):
            raise ValueError(f"Time slot conflict: {meeting.meeting_datetime} - {end_time}")
        
        # Create calendar event
        calendar_event = CalendarEvent(
            title=f"Meeting: {meeting.title}",
            description=f"Blocked for meeting: {meeting.description or meeting.title}",
            start_datetime=meeting.meeting_datetime,
            end_datetime=end_time,
            event_type="meeting_block",
            session_meeting_id=meeting.id,
            is_auto_generated=True,
            created_by_admin_id=created_by_id if user_type == "Admin" else None,
            created_by_presenter_id=created_by_id if user_type == "Presenter" else None,
            created_by_mentor_id=created_by_id if user_type == "Mentor" else None
        )
        
        db.add(calendar_event)
        db.commit()
        db.refresh(calendar_event)
        
        return calendar_event.id
    
    @staticmethod
    def update_session_block(db: Session, session: SessionModel, original_time: datetime) -> bool:
        """Update calendar block when session is rescheduled"""
        if not session.scheduled_time:
            return False
            
        # Find existing block
        existing_block = db.query(CalendarEvent).filter(
            CalendarEvent.event_type == "session_block",
            CalendarEvent.start_datetime == original_time,
            CalendarEvent.is_auto_generated == True
        ).first()
        
        if existing_block:
            new_end_time = session.scheduled_time + timedelta(minutes=session.duration_minutes or 120)
            
            # Check for conflicts (excluding current block)
            if CalendarBlockingService.check_time_conflict(db, session.scheduled_time, new_end_time, existing_block.id):
                raise ValueError(f"Time slot conflict: {session.scheduled_time} - {new_end_time}")
            
            # Update block
            existing_block.title = f"Session: {session.title}"
            existing_block.description = f"Blocked for session: {session.description or session.title}"
            existing_block.start_datetime = session.scheduled_time
            existing_block.end_datetime = new_end_time
            existing_block.updated_at = datetime.utcnow()
            
            db.commit()
            return True
            
        return False
    
    @staticmethod
    def update_meeting_block(db: Session, meeting: SessionMeeting, original_time: datetime) -> bool:
        """Update calendar block when meeting is rescheduled"""
        if not meeting.meeting_datetime:
            return False
            
        # Find existing block
        existing_block = db.query(CalendarEvent).filter(
            CalendarEvent.session_meeting_id == meeting.id,
            CalendarEvent.is_auto_generated == True
        ).first()
        
        if existing_block:
            new_end_time = meeting.meeting_datetime + timedelta(minutes=meeting.duration_minutes or 60)
            
            # Check for conflicts (excluding current block)
            if CalendarBlockingService.check_time_conflict(db, meeting.meeting_datetime, new_end_time, existing_block.id):
                raise ValueError(f"Time slot conflict: {meeting.meeting_datetime} - {new_end_time}")
            
            # Update block
            existing_block.title = f"Meeting: {meeting.title}"
            existing_block.description = f"Blocked for meeting: {meeting.description or meeting.title}"
            existing_block.start_datetime = meeting.meeting_datetime
            existing_block.end_datetime = new_end_time
            existing_block.updated_at = datetime.utcnow()
            
            db.commit()
            return True
            
        return False
    
    @staticmethod
    def delete_session_block(db: Session, session_id: int) -> bool:
        """Delete calendar block when session is deleted"""
        blocks = db.query(CalendarEvent).filter(
            CalendarEvent.event_type == "session_block",
            CalendarEvent.is_auto_generated == True,
            CalendarEvent.title.like(f"%Session%")
        ).all()
        
        deleted = False
        for block in blocks:
            if f"session_{session_id}" in block.description or str(session_id) in block.description:
                db.delete(block)
                deleted = True
        
        if deleted:
            db.commit()
        return deleted
    
    @staticmethod
    def delete_meeting_block(db: Session, meeting_id: int) -> bool:
        """Delete calendar block when meeting is deleted"""
        block = db.query(CalendarEvent).filter(
            CalendarEvent.session_meeting_id == meeting_id,
            CalendarEvent.is_auto_generated == True
        ).first()
        
        if block:
            db.delete(block)
            db.commit()
            return True
        return False
    
    @staticmethod
    def get_blocked_slots(db: Session, start_date: datetime, end_date: datetime) -> List[dict]:
        """Get all blocked time slots in a date range"""
        blocked_events = db.query(CalendarEvent).filter(
            CalendarEvent.start_datetime >= start_date,
            CalendarEvent.start_datetime <= end_date,
            CalendarEvent.event_type.in_(["session_block", "meeting_block"])
        ).all()
        
        blocked_sessions = db.query(SessionModel).filter(
            SessionModel.scheduled_time >= start_date,
            SessionModel.scheduled_time <= end_date,
            SessionModel.scheduled_time.isnot(None)
        ).all()
        
        blocked_meetings = db.query(SessionMeeting).filter(
            SessionMeeting.meeting_datetime >= start_date,
            SessionMeeting.meeting_datetime <= end_date,
            SessionMeeting.meeting_datetime.isnot(None)
        ).all()
        
        blocked_slots = []
        
        # Add calendar events
        for event in blocked_events:
            blocked_slots.append({
                "id": f"event_{event.id}",
                "type": "calendar_event",
                "title": event.title,
                "start_datetime": event.start_datetime,
                "end_datetime": event.end_datetime,
                "is_blocked": True
            })
        
        # Add sessions
        for session in blocked_sessions:
            end_time = session.scheduled_time + timedelta(minutes=session.duration_minutes or 120)
            blocked_slots.append({
                "id": f"session_{session.id}",
                "type": "session",
                "title": f"Session: {session.title}",
                "start_datetime": session.scheduled_time,
                "end_datetime": end_time,
                "is_blocked": True
            })
        
        # Add meetings
        for meeting in blocked_meetings:
            end_time = meeting.meeting_datetime + timedelta(minutes=meeting.duration_minutes or 60)
            blocked_slots.append({
                "id": f"meeting_{meeting.id}",
                "type": "meeting",
                "title": f"Meeting: {meeting.title}",
                "start_datetime": meeting.meeting_datetime,
                "end_datetime": end_time,
                "is_blocked": True
            })
        
        return sorted(blocked_slots, key=lambda x: x["start_datetime"])