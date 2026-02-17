
from database import SessionLocal, CourseAssignment, User
import sys

def check_assignments():
    db = SessionLocal()
    try:
        assignments = db.query(CourseAssignment).all()
        print(f"Total assignments: {len(assignments)}")
        for a in assignments:
            print(f"ID: {a.id}, CourseID: {a.course_id}, Type: {a.assignment_type}, UserID: {a.user_id}, College: {a.college}")
            
        # Check student college
        students = db.query(User).filter(User.role == 'Student').all()
        print(f"\nStudents: {len(students)}")
        for s in students:
            print(f"ID: {s.id}, Username: {s.username}, College: '{s.college}'")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_assignments()
