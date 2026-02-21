
from sqlalchemy.orm import Session
from database import SessionLocal, EmailTemplate, User, UserCohort, Enrollment
from cohort_specific_models import CohortSpecificCourse
import json

def check_db():
    db = SessionLocal()
    try:
        print("--- Checking Email Template Status ---")
        t = db.query(EmailTemplate).filter(EmailTemplate.name == "New Resource Added Notification").first()
        if t:
            print(f"Template Found: {t.name}, Is Active: {t.is_active}, Category: {t.category}")
        else:
            print("Template NOT FOUND!")
            
        print("\n--- Checking Cohort 18 Students ---")
        cohort_students = db.query(User).join(UserCohort).filter(UserCohort.cohort_id == 18).all()
        print(f"Total students in Cohort 18: {len(cohort_students)}")
        for s in cohort_students:
            print(f"ID: {s.id}, Username: {s.username}, Role: {s.role}, UserType: {s.user_type}")

        print("\n--- Checking Cohort 18 Courses ---")
        courses = db.query(CohortSpecificCourse).filter(CohortSpecificCourse.cohort_id == 18).all()
        for c in courses:
            print(f"Course ID: {c.id}, Title: {c.title}")

    finally:
        db.close()

if __name__ == "__main__":
    check_db()
