
from database import get_db, Enrollment, User
from sqlalchemy.orm import Session
from cohort_specific_models import CohortSpecificEnrollment

def check_enrollments():
    db = next(get_db())
    
    print("--- Global Enrollments ---")
    enrollments = db.query(Enrollment).all()
    for e in enrollments[:10]:
        print(f"Student ID: {e.student_id} | Course ID: {e.course_id}")
    print(f"Total: {len(enrollments)}")
    
    print("\n--- Cohort Course Enrollments ---")
    c_enrollments = db.query(CohortSpecificEnrollment).all()
    for e in c_enrollments[:10]:
        print(f"Student ID: {e.student_id} | Cohort Course ID: {e.course_id}")
    print(f"Total: {len(c_enrollments)}")

if __name__ == "__main__":
    check_enrollments()
