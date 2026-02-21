
from sqlalchemy.orm import Session
from database import SessionLocal, EmailTemplate, User, UserCohort, Enrollment
import json

def check_db():
    db = SessionLocal()
    try:
        print("--- Checking Email Templates ---")
        templates = db.query(EmailTemplate).all()
        for t in templates:
            print(f"Name: {t.name}, Category: {t.category}, Is Active: {t.is_active}")
            
        print("\n--- Checking Users (Students) ---")
        students = db.query(User).filter(User.user_type == "Student").all()
        print(f"Found {len(students)} Student user_type records")
        for s in students:
            print(f"ID: {s.id}, Username: {s.username}, Role: {s.role}")
            
        print("\n--- Checking Enrollment for Global Courses (Student ID 1 sample) ---")
        enrollments = db.query(Enrollment).all()
        print(f"Total Enrollments: {len(enrollments)}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_db()
