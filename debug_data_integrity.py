
from database import SessionLocal, CourseAssignment, User, Course
import sys

def check_data_integrity():
    db = SessionLocal()
    try:
        print("--- ASSIGNMENTS ---")
        assignments = db.query(CourseAssignment).all()
        for a in assignments:
            print(f"AssignID: {a.id}, Type: '{a.assignment_type}', College: '{a.college}', UserID: {a.user_id}, CourseID: {a.course_id}")

        print("\n--- USERS ---")
        users = db.query(User).filter(User.role == 'Student').all()
        for u in users:
            print(f"UserID: {u.id}, Name: {u.username}, College: '{u.college}', Role: {u.role}")

        print("\n--- COURSES ---")
        courses = db.query(Course).all()
        for c in courses:
             print(f"CourseID: {c.id}, Active: {c.is_active}, Title: {c.title}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_data_integrity()
