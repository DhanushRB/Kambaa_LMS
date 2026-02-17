import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import User, Enrollment, Course, Session as SessionModel, Module, CohortCourse, UserCohort
from cohort_specific_models import CohortSpecificEnrollment, CohortSpecificCourse, CohortCourseSession, CohortCourseModule
from feedback_models import FeedbackForm
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def debug_student_feedback(student_id):
    print(f"--- Debugging Student ID: {student_id} ---")
    
    # 1. Check user
    user = db.query(User).filter(User.id == student_id).first()
    if not user:
        print("Student not found!")
        return
    print(f"User: {user.username}, Role: {user.role}, Cohort ID: {user.cohort_id}")
    
    # 2. Check direct enrollments
    enrollments = db.query(Enrollment).filter(Enrollment.student_id == student_id).all()
    print(f"Direct Enrollments: {[e.course_id for e in enrollments]}")
    
    # 3. Check cohorts
    user_cohorts = db.query(UserCohort).filter(UserCohort.user_id == student_id).all()
    cohort_ids = [uc.cohort_id for uc in user_cohorts]
    print(f"User Cohorts: {cohort_ids}")
    
    # 4. Check courses assigned to these cohorts
    cohort_course_ids = []
    if cohort_ids:
        # Legacy CohortCourse
        cc_assignments = db.query(CohortCourse).filter(CohortCourse.cohort_id.in_(cohort_ids)).all()
        for cc in cc_assignments:
            if cc.course_id not in cohort_course_ids:
                cohort_course_ids.append(cc.course_id)
        
        # Unified CourseAssignment
        try:
            from database import CourseAssignment
            unified_assignments = db.query(CourseAssignment).filter(
                CourseAssignment.cohort_id.in_(cohort_ids),
                CourseAssignment.assignment_type == 'cohort'
            ).all()
            for ua in unified_assignments:
                if ua.course_id not in cohort_course_ids:
                    cohort_course_ids.append(ua.course_id)
        except ImportError:
            pass
            
    # 5. Check cohort-specific courses in these cohorts
    cs_course_ids = []
    if cohort_ids:
        cs_courses = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.cohort_id.in_(cohort_ids),
            CohortSpecificCourse.is_active == True
        ).all()
        cs_course_ids = [c.id for c in cs_courses]
    
    # Also check direct enrollments for both
    enrollment_course_ids = [e.course_id for e in enrollments]
    all_regular_course_ids = list(set(enrollment_course_ids + cohort_course_ids))
    
    cs_enrollments = db.query(CohortSpecificEnrollment).filter(CohortSpecificEnrollment.student_id == student_id).all()
    all_cs_course_ids = list(set(cs_course_ids + [e.course_id for e in cs_enrollments]))
    
    print(f"Regular Course IDs: {all_regular_course_ids}")
    print(f"Cohort-specific Course IDs: {all_cs_course_ids}")
    
    # 6. Check sessions and forms for all identified courses
    if all_regular_course_ids:
        sessions = db.query(SessionModel).join(Module).filter(Module.course_id.in_(all_regular_course_ids)).all()
        session_ids = [s.id for s in sessions]
        print(f"Found {len(session_ids)} global sessions.")
        
        forms = db.query(FeedbackForm).filter(FeedbackForm.session_id.in_(session_ids), FeedbackForm.session_type == 'global').all()
        print(f"Found {len(forms)} global feedback forms: {[f.id for f in forms]}")
            
    if all_cs_course_ids:
        cs_sessions = db.query(CohortCourseSession).join(CohortCourseModule).filter(CohortCourseModule.course_id.in_(all_cs_course_ids)).all()
        cs_session_ids = [s.id for s in cs_sessions]
        print(f"Found {len(cs_session_ids)} cohort sessions.")
        
        cs_forms = db.query(FeedbackForm).filter(FeedbackForm.session_id.in_(cs_session_ids), FeedbackForm.session_type == 'cohort').all()
        print(f"Found {len(cs_forms)} cohort feedback forms: {[f.id for f in cs_forms]}")
        for f in cs_forms:
            print(f"  Form ID: {f.id}, Session ID: {f.session_id}, Active: {f.is_active}, Title: {f.title}")

def find_active_student():
    print("\n--- Finding an active student with any course access ---")
    # Try finding someone with an enrollment
    e = db.query(Enrollment).first()
    if e:
        print(f"Found student {e.student_id} from direct enrollment.")
        return e.student_id
    
    # Try finding someone in a cohort with assigned courses
    ca = db.query(CohortCourse).first()
    if ca:
        uc = db.query(UserCohort).filter(UserCohort.cohort_id == ca.cohort_id).first()
        if uc:
            print(f"Found student {uc.user_id} from cohort-assigned course.")
            return uc.user_id
            
    # Try cohort-specific
    cse = db.query(CohortSpecificEnrollment).first()
    if cse:
        print(f"Found student {cse.student_id} from cohort-specific enrollment.")
        return cse.student_id

    print("No students found with course access.")
    return None

if __name__ == "__main__":
    active_id = find_active_student()
    if active_id:
        debug_student_feedback(active_id)
    
    # Also check Student 75 as requested by previous tests
    print("\n--- Final check for Student 75 ---")
    debug_student_feedback(75)
        
    db.close()
