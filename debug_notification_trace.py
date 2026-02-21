
from sqlalchemy.orm import Session
from database import SessionLocal, EmailTemplate, User, UserCohort, Enrollment, Session as RegularSession, Module
from cohort_specific_models import CohortSpecificCourse, CohortCourseSession, CohortCourseModule
import json

def check_db():
    db = SessionLocal()
    try:
        print("--- Template Check ---")
        t = db.query(EmailTemplate).filter(EmailTemplate.name == "New Resource Added Notification").first()
        if t:
            print(f"Template '{t.name}' exists and is_active={t.is_active}")
        else:
            print("Template 'New Resource Added Notification' MISSING from database")

        print("\n--- Session 346 Trace ---")
        # Check if it's a cohort session
        cs = db.query(CohortCourseSession).filter(CohortCourseSession.id == 346).first()
        if cs:
            print(f"Session 346 is a COHORT session: {cs.title}")
            cm = db.query(CohortCourseModule).filter(CohortCourseModule.id == cs.module_id).first()
            if cm:
                print(f"Module: {cm.title}, Course ID: {cm.course_id}")
                cc = db.query(CohortSpecificCourse).filter(CohortSpecificCourse.id == cm.course_id).first()
                if cc:
                    print(f"Course: {cc.title}, Cohort ID: {cc.cohort_id}")
                    # Check students in this cohort
                    students = db.query(User).join(UserCohort).filter(UserCohort.cohort_id == cc.cohort_id).all()
                    print(f"Students found in cohort {cc.cohort_id}: {len(students)}")
                    for s in students:
                        print(f"  - {s.username}: Role={s.role}, UserType={s.user_type}, Email={s.email}")
                else:
                    print(f"CohortSpecificCourse {cm.course_id} NOT FOUND")
            else:
                print(f"CohortCourseModule {cs.module_id} NOT FOUND")
        else:
            # Check if it's a regular session
            rs = db.query(RegularSession).filter(RegularSession.id == 346).first()
            if rs:
                print(f"Session 346 is a GLOBAL session: {rs.title}")
                rm = db.query(Module).filter(Module.id == rs.module_id).first()
                if rm:
                    print(f"Module: {rm.title}, Course ID: {rm.course_id}")
                    # In email_utils.py, regular_course = db.query(Course).filter(Course.id == regular_module.course_id).first()
                    # Need to check global enrollments
                    enrollments = db.query(Enrollment).filter(Enrollment.course_id == rm.course_id).all()
                    print(f"Enrollments for course {rm.course_id}: {len(enrollments)}")
            else:
                print("Session 346 NOT FOUND in either table")

    finally:
        db.close()

if __name__ == "__main__":
    check_db()
