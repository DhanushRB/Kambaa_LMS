
from database import get_db, Session as SessionModel, CalendarEvent
from sqlalchemy.orm import Session
from datetime import datetime, date
from assignment_quiz_models import Assignment, Quiz
from cohort_specific_models import CohortCourseSession

def check_all_data():
    db = next(get_db())
    
    print("--- GLOBAL SESSIONS ---")
    sessions = db.query(SessionModel).all()
    for s in sessions[:10]:
        print(f"Session: {s.title} | Date: {s.scheduled_time}")
    print(f"Total Global Sessions: {len(sessions)}")
    
    print("\n--- COHORT SESSIONS ---")
    c_sessions = db.query(CohortCourseSession).all()
    for s in c_sessions[:10]:
        print(f"Cohort Session: {s.title} | Date: {s.scheduled_time}")
    print(f"Total Cohort Sessions: {len(c_sessions)}")
    
    print("\n--- ASSIGNMENTS ---")
    assignments = db.query(Assignment).all()
    for a in assignments[:10]:
        print(f"Assignment: {a.title} | Due: {a.due_date} | Type: {a.session_type}")
    print(f"Total Assignments: {len(assignments)}")
    
    print("\n--- QUIZZES ---")
    quizzes = db.query(Quiz).all()
    for q in quizzes[:10]:
        print(f"Quiz: {q.title} | Created: {q.created_at}")
    print(f"Total Quizzes: {len(quizzes)}")

if __name__ == "__main__":
    check_all_data()
