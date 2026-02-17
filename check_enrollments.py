import sys
import os

# Add backend to path
sys.path.append(r"D:\LMS-v2\backend")

from database import SessionLocal, User, Enrollment
from cohort_specific_models import CohortSpecificEnrollment

def check_enrollments():
    db = SessionLocal()
    try:
        print("--- Global Enrollments ---")
        g_enrolls = db.query(Enrollment).all()
        print(f"Total Global Enrollments: {len(g_enrolls)}")
        for e in g_enrolls[:10]:
            print(f"  - Cohort={e.cohort_id}, Course={e.course_id}, Student={e.student_id}")

        print("\n--- Cohort Specific Enrollments ---")
        s_enrolls = db.query(CohortSpecificEnrollment).all()
        print(f"Total Specific Enrollments: {len(s_enrolls)}")
        for e in s_enrolls[:10]:
             print(f"  - Course={e.course_id}, Student={e.student_id}")
             
        # Check cohort 16 specifically
        print("\n--- Filtered (Cohort 16 / Course 15) ---")
        match_g = db.query(Enrollment).filter(Enrollment.cohort_id == 16, Enrollment.course_id == 15).count()
        match_s = db.query(CohortSpecificEnrollment).filter(CohortSpecificEnrollment.course_id == 15).count()
        print(f"Global matches for C16/C15: {match_g}")
        print(f"Specific matches for Course 15: {match_s}")

    finally:
        db.close()

if __name__ == "__main__":
    check_enrollments()
