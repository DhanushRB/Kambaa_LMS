
from database import get_db, Session as SessionModel, CalendarEvent
from sqlalchemy.orm import Session
from datetime import datetime, date
from assignment_quiz_models import Assignment, Quiz
from cohort_specific_models import CohortCourseSession

def check_all_data():
    db = next(get_db())
    
    print("--- GLOBAL SESSIONS ---")
    sessions = db.query(SessionModel).all()
    for s in sessions:
        print(f"ID: {s.id} | Date: {s.scheduled_time}")
    print(f"Total: {len(sessions)}")
    
    print("\n--- COHORT SESSIONS ---")
    c_sessions = db.query(CohortCourseSession).all()
    for s in c_sessions:
        print(f"ID: {s.id} | Date: {s.scheduled_time}")
    print(f"Total: {len(c_sessions)}")
    
    print("\n--- ASSIGNMENTS ---")
    assignments = db.query(Assignment).all()
    for a in assignments:
        print(f"ID: {a.id} | Due: {a.due_date}")
    print(f"Total: {len(assignments)}")
    
    print("\n--- QUIZZES ---")
    quizzes = db.query(Quiz).all()
    for q in quizzes:
        print(f"ID: {q.id} | Created: {q.created_at}")
    print(f"Total: {len(quizzes)}")

if __name__ == "__main__":
    check_all_data()
