
from database import get_db, Session as SessionModel, CalendarEvent, Course, Module
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from assignment_quiz_models import Assignment, Quiz
from cohort_specific_models import CohortCourseSession

def debug():
    db = next(get_db())
    start = datetime(2026, 3, 1)
    end = datetime(2026, 3, 31)
    
    print(f"--- Searching for March 2026 (01 to 31) ---")
    
    # 1. Global Sessions
    sessions = db.query(SessionModel).filter(SessionModel.scheduled_time >= start, SessionModel.scheduled_time <= end).all()
    print(f"Global Sessions found: {len(sessions)}")
    
    # 2. Cohort Sessions
    c_sessions = db.query(CohortCourseSession).filter(CohortCourseSession.scheduled_time >= start, CohortCourseSession.scheduled_time <= end).all()
    print(f"Cohort Sessions found: {len(c_sessions)}")
    
    # 3. Assignments
    assignments = db.query(Assignment).filter(Assignment.due_date >= start, Assignment.due_date <= end).all()
    print(f"Assignments found: {len(assignments)}")
    
    # 4. Quizzes
    quizzes = db.query(Quiz).filter(Quiz.created_at >= start, Quiz.created_at <= end).all()
    print(f"Quizzes found: {len(quizzes)}")
    
    # 5. Calendar Events
    events = db.query(CalendarEvent).filter(CalendarEvent.start_datetime >= start, CalendarEvent.start_datetime <= end).all()
    print(f"Calendar Events found: {len(events)}")

if __name__ == "__main__":
    debug()
