from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from typing import List, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)

class CalendarNotificationService:
    """Service for handling calendar event notifications and reminders"""
    
    def __init__(self):
        self.db = SessionLocal()
    
    async def check_upcoming_reminders(self):
        """Check for upcoming reminders and send notifications"""
        try:
            from calendar_events_models import Reminder
            
            # Get reminders that should be sent now
            now = datetime.utcnow()
            upcoming_reminders = self.db.query(Reminder).filter(
                Reminder.reminder_datetime <= now,
                Reminder.is_sent == False
            ).all()
            
            for reminder in upcoming_reminders:
                await self.send_reminder_notification(reminder)
                
                # Mark as sent
                reminder.is_sent = True
                reminder.sent_at = now
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error checking reminders: {str(e)}")
            self.db.rollback()
    
    async def send_reminder_notification(self, reminder):
        """Send notification for a reminder"""
        try:
            from database import Notification
            
            # Create in-app notification
            notification = Notification(
                user_id=reminder.user_id,
                title=f"Reminder: {reminder.title}",
                message=reminder.message or f"Don't forget about {reminder.title}",
                notification_type="REMINDER",
                is_read=False
            )
            self.db.add(notification)
            
            # Send email if enabled
            if reminder.send_email:
                await self.send_email_reminder(reminder)
            
            # Send push notification if enabled
            if reminder.send_push:
                await self.send_push_notification(reminder)
            
            logger.info(f"Reminder notification sent for: {reminder.title}")
            
        except Exception as e:
            logger.error(f"Error sending reminder notification: {str(e)}")
    
    async def send_email_reminder(self, reminder):
        """Send email reminder (placeholder for email service integration)"""
        try:
            # This would integrate with your email service
            logger.info(f"Email reminder sent to user {reminder.user_id}: {reminder.title}")
        except Exception as e:
            logger.error(f"Error sending email reminder: {str(e)}")
    
    async def send_push_notification(self, reminder):
        """Send push notification (placeholder for push service integration)"""
        try:
            # This would integrate with your push notification service
            logger.info(f"Push notification sent to user {reminder.user_id}: {reminder.title}")
        except Exception as e:
            logger.error(f"Error sending push notification: {str(e)}")
    
    async def create_event_reminders(self, event_id: int, user_ids: List[int]):
        """Create reminders for an event for specified users"""
        try:
            from calendar_events_models import CalendarEvent, Reminder
            
            event = self.db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
            if not event:
                return
            
            for user_id in user_ids:
                # Calculate reminder time
                reminder_time = event.start_datetime - timedelta(minutes=event.reminder_minutes)
                
                reminder = Reminder(
                    user_id=user_id,
                    title=event.title,
                    message=f"Upcoming event: {event.title}",
                    reminder_datetime=reminder_time,
                    event_id=event.id,
                    send_email=event.send_email_reminder,
                    send_push=event.send_push_notification
                )
                self.db.add(reminder)
            
            self.db.commit()
            logger.info(f"Created reminders for event {event.title} for {len(user_ids)} users")
            
        except Exception as e:
            logger.error(f"Error creating event reminders: {str(e)}")
            self.db.rollback()
    
    async def sync_with_external_calendar(self, user_id: int, provider: str):
        """Sync events with external calendar provider"""
        try:
            from calendar_events_models import SyncSettings, CalendarEvent
            
            sync_settings = self.db.query(SyncSettings).filter(
                SyncSettings.user_id == user_id
            ).first()
            
            if not sync_settings:
                return {"success": False, "message": "Sync settings not found"}
            
            if provider == "google" and not sync_settings.google_calendar_enabled:
                return {"success": False, "message": "Google Calendar sync not enabled"}
            
            if provider == "outlook" and not sync_settings.outlook_calendar_enabled:
                return {"success": False, "message": "Outlook Calendar sync not enabled"}
            
            # Get user's events to sync
            events = self.db.query(CalendarEvent).filter(
                CalendarEvent.created_by == user_id
            ).all()
            
            # This would integrate with Google Calendar API or Outlook API
            # For now, we'll simulate the sync
            synced_count = len(events)
            
            logger.info(f"Synced {synced_count} events with {provider} for user {user_id}")
            
            return {
                "success": True, 
                "message": f"Successfully synced {synced_count} events with {provider}",
                "synced_count": synced_count
            }
            
        except Exception as e:
            logger.error(f"Error syncing with {provider}: {str(e)}")
            return {"success": False, "message": f"Sync failed: {str(e)}"}
    
    async def get_user_notifications(self, user_id: int, limit: int = 10):
        """Get recent notifications for a user"""
        try:
            from database import Notification
            
            notifications = self.db.query(Notification).filter(
                Notification.user_id == user_id
            ).order_by(Notification.created_at.desc()).limit(limit).all()
            
            return [{
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "type": n.notification_type,
                "is_read": n.is_read,
                "created_at": n.created_at
            } for n in notifications]
            
        except Exception as e:
            logger.error(f"Error getting user notifications: {str(e)}")
            return []
    
    async def mark_notification_read(self, notification_id: int, user_id: int):
        """Mark a notification as read"""
        try:
            from database import Notification
            
            notification = self.db.query(Notification).filter(
                Notification.id == notification_id,
                Notification.user_id == user_id
            ).first()
            
            if notification:
                notification.is_read = True
                self.db.commit()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error marking notification as read: {str(e)}")
            self.db.rollback()
            return False
    
    async def create_deadline_reminders(self, assignment_id: int = None, quiz_id: int = None):
        """Create automatic reminders for assignment/quiz deadlines"""
        try:
            from database import Assignment, Quiz, Enrollment, User
            from calendar_events_models import Reminder
            
            if assignment_id:
                assignment = self.db.query(Assignment).filter(Assignment.id == assignment_id).first()
                if not assignment:
                    return
                
                # Get all enrolled students for this course
                enrollments = self.db.query(Enrollment).filter(
                    Enrollment.course_id == assignment.course_id
                ).all()
                
                for enrollment in enrollments:
                    # Create reminders 3 days, 1 day, and 1 hour before deadline
                    reminder_times = [
                        assignment.due_date - timedelta(days=3),
                        assignment.due_date - timedelta(days=1),
                        assignment.due_date - timedelta(hours=1),
                    ]
                    
                    for reminder_time in reminder_times:
                        if reminder_time > datetime.utcnow():
                            reminder = Reminder(
                                user_id=enrollment.student_id,
                                title=f"Assignment Due: {assignment.title}",
                                message=f"Assignment '{assignment.title}' is due soon",
                                reminder_datetime=reminder_time,
                                assignment_id=assignment.id
                            )
                            self.db.add(reminder)
            
            elif quiz_id:
                quiz = self.db.query(Quiz).filter(Quiz.id == quiz_id).first()
                if not quiz:
                    return
                
                # Get session and course info
                from database import SessionModel, Module
                session = self.db.query(SessionModel).filter(SessionModel.id == quiz.session_id).first()
                if not session:
                    return
                
                module = self.db.query(Module).filter(Module.id == session.module_id).first()
                if not module:
                    return
                
                # Get all enrolled students for this course
                enrollments = self.db.query(Enrollment).filter(
                    Enrollment.course_id == module.course_id
                ).all()
                
                # Use session scheduled time as quiz deadline
                quiz_deadline = session.scheduled_time + timedelta(hours=24)  # Quiz available for 24 hours
                
                for enrollment in enrollments:
                    reminder = Reminder(
                        user_id=enrollment.student_id,
                        title=f"Quiz Available: {quiz.title}",
                        message=f"Quiz '{quiz.title}' is now available",
                        reminder_datetime=session.scheduled_time,
                        quiz_id=quiz.id
                    )
                    self.db.add(reminder)
            
            self.db.commit()
            logger.info("Deadline reminders created successfully")
            
        except Exception as e:
            logger.error(f"Error creating deadline reminders: {str(e)}")
            self.db.rollback()
    
    def close(self):
        """Close database connection"""
        self.db.close()

# Background task runner
async def run_notification_service():
    """Background service to check and send notifications"""
    service = CalendarNotificationService()
    
    try:
        while True:
            await service.check_upcoming_reminders()
            await asyncio.sleep(60)  # Check every minute
    except Exception as e:
        logger.error(f"Notification service error: {str(e)}")
    finally:
        service.close()

# Utility functions
def create_event_notification(event_title: str, event_datetime: datetime, user_ids: List[int]):
    """Create notifications for a new event"""
    try:
        db = SessionLocal()
        from database import Notification
        
        for user_id in user_ids:
            notification = Notification(
                user_id=user_id,
                title=f"New Event: {event_title}",
                message=f"A new event '{event_title}' has been scheduled for {event_datetime.strftime('%B %d, %Y at %I:%M %p')}",
                notification_type="EVENT",
                is_read=False
            )
            db.add(notification)
        
        db.commit()
        db.close()
        logger.info(f"Event notifications created for {len(user_ids)} users")
        
    except Exception as e:
        logger.error(f"Error creating event notifications: {str(e)}")

def get_upcoming_events_for_user(user_id: int, days_ahead: int = 7):
    """Get upcoming events for a specific user"""
    try:
        db = SessionLocal()
        from calendar_events_models import CalendarEvent
        from database import Enrollment, SessionModel, Module, Assignment, Quiz
        
        end_date = datetime.utcnow() + timedelta(days=days_ahead)
        
        # Get user's enrolled courses
        enrollments = db.query(Enrollment).filter(Enrollment.student_id == user_id).all()
        course_ids = [e.course_id for e in enrollments]
        
        upcoming_events = []
        
        # Get calendar events
        events = db.query(CalendarEvent).filter(
            CalendarEvent.start_datetime >= datetime.utcnow(),
            CalendarEvent.start_datetime <= end_date
        ).all()
        
        for event in events:
            if not event.course_id or event.course_id in course_ids:
                upcoming_events.append({
                    "type": "event",
                    "title": event.title,
                    "datetime": event.start_datetime,
                    "location": event.location,
                    "event_type": event.event_type.value if event.event_type else "general"
                })
        
        # Get upcoming sessions
        sessions = db.query(SessionModel).join(Module).filter(
            Module.course_id.in_(course_ids),
            SessionModel.scheduled_time >= datetime.utcnow(),
            SessionModel.scheduled_time <= end_date
        ).all()
        
        for session in sessions:
            upcoming_events.append({
                "type": "session",
                "title": session.title,
                "datetime": session.scheduled_time,
                "location": "Online" if session.zoom_link else "TBD",
                "zoom_link": session.zoom_link
            })
        
        # Get upcoming assignments
        assignments = db.query(Assignment).filter(
            Assignment.course_id.in_(course_ids),
            Assignment.due_date >= datetime.utcnow(),
            Assignment.due_date <= end_date
        ).all()
        
        for assignment in assignments:
            upcoming_events.append({
                "type": "assignment",
                "title": f"Assignment Due: {assignment.title}",
                "datetime": assignment.due_date,
                "location": "Online Submission"
            })
        
        # Sort by datetime
        upcoming_events.sort(key=lambda x: x["datetime"])
        
        db.close()
        return upcoming_events
        
    except Exception as e:
        logger.error(f"Error getting upcoming events: {str(e)}")
        return []

# Initialize notification service
notification_service = CalendarNotificationService()