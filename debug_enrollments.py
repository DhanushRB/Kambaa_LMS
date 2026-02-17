from database import SessionLocal
from cohort_specific_models import CohortSpecificEnrollment, CohortSpecificCourse
from assignment_quiz_models import Assignment
from database import User

db = SessionLocal()

print("=== Students in Cohort 16 ===")
students = db.query(User).filter(User.cohort_id == 16).all()
for s in students:
    print(f"Student ID: {s.id}, Name: {s.username}, Email: {s.email}")

print("\n=== Cohort-Specific Course 15 ===")
course = db.query(CohortSpecificCourse).filter(CohortSpecificCourse.id == 15).first()
if course:
    print(f"Course ID: {course.id}, Title: {course.title}, Cohort ID: {course.cohort_id}")

print("\n=== Enrollments in Course 15 ===")
enrollments = db.query(CohortSpecificEnrollment).filter(CohortSpecificEnrollment.course_id == 15).all()
if enrollments:
    for e in enrollments:
        print(f"Student ID: {e.student_id}, Course ID: {e.course_id}")
else:
    print("NO ENROLLMENTS FOUND!")

print("\n=== Assignments in Session 250 ===")
assignments = db.query(Assignment).filter(Assignment.session_id == 250).all()
if assignments:
    for a in assignments:
        print(f"Assignment ID: {a.id}, Title: {a.title}, Session Type: {a.session_type}, Active: {a.is_active}")
else:
    print("NO ASSIGNMENTS FOUND!")

db.close()
