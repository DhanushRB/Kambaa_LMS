
import traceback
from database import get_db, Session as SessionModel, Module, Course, CalendarEvent
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from assignment_quiz_models import Assignment, Quiz
from cohort_specific_models import CohortCourseSession, CohortCourseModule

def insert_test_data():
    try:
        db = next(get_db())
        
        # 1. Global Session for March 10, 2026
        new_session = SessionModel(
            module_id=41,
            title="Test Global Session: Calendar Integration",
            description="Verify this shows up in March 2026 calendar",
            scheduled_time=datetime(2026, 3, 10, 10, 0, 0),
            duration_minutes=60,
            session_number=1
        )
        db.add(new_session)
        
        # 2. Assignment for March 15, 2026
        db.flush()
        new_assignment = Assignment(
            session_id=new_session.id,
            title="Test Assignment: Calendar Check",
            description="Due on March 15",
            due_date=datetime(2026, 3, 15, 23, 59, 59),
            session_type="global",
            created_by=2, # Admin ID from previous check
            total_marks=100
        )
        db.add(new_assignment)
        
        # 3. Cohort Specific Session for March 12, 2026
        new_cohort_session = CohortCourseSession(
            module_id=173,
            title="Test Cohort Session: March 12",
            description="Verify cohort specific session display",
            scheduled_time=datetime(2026, 3, 12, 14, 0, 0),
            duration_minutes=90,
            session_number=1
        )
        db.add(new_cohort_session)
        
        # 4. General Calendar Event for March 20, 2026
        new_event = CalendarEvent(
            title="General Academy Event",
            description="Global event for all students",
            start_datetime=datetime(2026, 3, 20, 9, 0, 0),
            end_datetime=datetime(2026, 3, 20, 17, 0, 0),
            event_type="general",
            is_all_day=False
        )
        db.add(new_event)
        
        db.commit()
        print("Test data inserted successfully for March 2026!")
    except Exception as e:
        print(f"FAILED TO INSERT TEST DATA:")
        traceback.print_exc()

if __name__ == "__main__":
    insert_test_data()
