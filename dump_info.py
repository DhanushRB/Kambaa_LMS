import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import User, Enrollment, Course, Session as SessionModel, Module, CohortCourse, UserCohort, Cohort
from cohort_specific_models import CohortSpecificEnrollment, CohortSpecificCourse, CohortCourseSession, CohortCourseModule
from feedback_models import FeedbackForm
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def dump_all_info():
    print("--- All Cohorts ---")
    cohorts = db.query(Cohort).all()
    for c in cohorts:
        print(f"ID: {c.id}, Name: {c.name}")
        
    print("\n--- All CohortCourse Assignments ---")
    cc = db.query(CohortCourse).all()
    for assignment in cc:
        print(f"Cohort ID: {assignment.cohort_id}, Course ID: {assignment.course_id}")
        
    print("\n--- All CourseAssignment Entries ---")
    try:
        from database import CourseAssignment
        ca = db.query(CourseAssignment).all()
        for a in ca:
            print(f"Cohort ID: {a.cohort_id}, Course ID: {a.course_id}, Type: {a.assignment_type}")
    except:
        print("CourseAssignment not found")
        
    print("\n--- Tracing Feedback Forms ---")
    forms = db.query(FeedbackForm).all()
    for f in forms:
        print(f"\nForm ID: {f.id}, Title: {f.title}, Type: {f.session_type}")
        if f.session_type == 'global':
            session = db.query(SessionModel).filter(SessionModel.id == f.session_id).first()
            if session:
                print(f"  Linked to Global Session: {session.id} ({session.title})")
                module = db.query(Module).filter(Module.id == session.module_id).first()
                if module:
                    course = db.query(Course).filter(Course.id == module.course_id).first()
                    if course:
                        print(f"  Linked to Global Course: {course.id} ({course.title})")
            else:
                print(f"  Global Session {f.session_id} NOT FOUND")
        else:
            session = db.query(CohortCourseSession).filter(CohortCourseSession.id == f.session_id).first()
            if session:
                print(f"  Linked to Cohort Session: {session.id} ({session.title})")
                module = db.query(CohortCourseModule).filter(CohortCourseModule.id == session.module_id).first()
                if module:
                    course = db.query(CohortSpecificCourse).filter(CohortSpecificCourse.id == module.course_id).first()
                    if course:
                        print(f"  Linked to Cohort Course: {course.id} ({course.title}) in Cohort {course.cohort_id}")
            else:
                print(f"  Cohort Session {f.session_id} NOT FOUND")

if __name__ == "__main__":
    dump_all_info()
    db.close()
