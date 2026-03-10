
from database import get_db, Course, Cohort, Module
from sqlalchemy.orm import Session
from cohort_specific_models import CohortSpecificCourse, CohortCourseModule

def get_ids():
    db = next(get_db())
    
    print("--- Global courses ---")
    courses = db.query(Course).limit(2).all()
    for c in courses:
        print(f"Course ID: {c.id} | Title: {c.title}")
        # Get a module for this course
        mod = db.query(Module).filter(Module.course_id == c.id).first()
        if mod:
            print(f"  Module ID: {mod.id} | Title: {mod.title}")
            
    print("\n--- Cohorts ---")
    cohorts = db.query(Cohort).limit(2).all()
    for ch in cohorts:
        print(f"Cohort ID: {ch.id} | Name: {ch.name}")
        
    print("\n--- Cohort Courses ---")
    cc = db.query(CohortSpecificCourse).limit(2).all()
    for c in cc:
        print(f"Cohort Course ID: {c.id} | Title: {c.title} | Cohort ID: {c.cohort_id}")
        # Get a module for this cohort course
        mod = db.query(CohortCourseModule).filter(CohortCourseModule.course_id == c.id).first()
        if mod:
            print(f"  Cohort Module ID: {mod.id} | Title: {mod.title}")

if __name__ == "__main__":
    get_ids()
