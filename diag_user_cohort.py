import sys
import os

# Add backend to path
sys.path.append(r"D:\LMS-v2\backend")

from database import SessionLocal, User, UserCohort

def check_user_cohort():
    db = SessionLocal()
    try:
        cohort_id = 16
        students = db.query(User).join(
            UserCohort, User.id == UserCohort.user_id
        ).filter(
            UserCohort.cohort_id == cohort_id,
            UserCohort.is_active == True
        ).all()
        
        print(f"DIAGNOSTIC: Students found in UserCohort for Cohort 16: {len(students)}")
        for s in students[:10]:
            print(f"  - ID={s.id}, Username='{s.username}', Email='{s.email}'")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_user_cohort()
