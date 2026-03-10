
from database import get_db, Session as SessionModel, CalendarEvent
from sqlalchemy.orm import Session
from datetime import datetime, date
from assignment_quiz_models import Assignment, Quiz

def check_events():
    db = next(get_db())
    start_date = datetime(2026, 3, 1)
    end_date = datetime(2026, 3, 31, 23, 59, 59)
    
    print(f"Checking events between {start_date} and {end_date}")
    
    events = db.query(CalendarEvent).filter(CalendarEvent.start_datetime >= start_date, CalendarEvent.start_datetime <= end_date).count()
    print(f"CalendarEvents: {events}")
    
    sessions = db.query(SessionModel).filter(SessionModel.scheduled_time >= start_date, SessionModel.scheduled_time <= end_date).count()
    print(f"Sessions: {sessions}")
    
    assignments = db.query(Assignment).filter(Assignment.due_date >= start_date, Assignment.due_date <= end_date).count()
    print(f"Assignments (Due Date): {assignments}")
    
    quizzes = db.query(Quiz).filter(Quiz.created_at >= start_date, Quiz.created_at <= end_date).count()
    print(f"Quizzes (Created At): {quizzes}")

if __name__ == "__main__":
    check_events()
