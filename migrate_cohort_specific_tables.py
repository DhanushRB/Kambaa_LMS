"""
Migration script to create cohort-specific course tables
Run this script to add the new tables for cohort-specific courses
"""

from sqlalchemy import create_engine
from database import Base
from cohort_specific_models import CohortSpecificCourse, CohortCourseModule, CohortCourseSession, CohortCourseResource
import os
from dotenv import load_dotenv

load_dotenv()

def migrate_cohort_specific_tables():
    """Create the new cohort-specific course tables"""
    try:
        DATABASE_URL = os.getenv("DATABASE_URL")
        engine = create_engine(DATABASE_URL)
        
        # Create only the new tables
        CohortSpecificCourse.__table__.create(engine, checkfirst=True)
        CohortCourseModule.__table__.create(engine, checkfirst=True)
        CohortCourseSession.__table__.create(engine, checkfirst=True)
        CohortCourseResource.__table__.create(engine, checkfirst=True)
        
        print("SUCCESS: Cohort-specific course tables created successfully!")
        print("Created tables:")
        print("   - cohort_specific_courses")
        print("   - cohort_course_modules")
        print("   - cohort_course_sessions")
        print("   - cohort_course_resources")
        
    except Exception as e:
        print(f"ERROR: Migration failed: {str(e)}")
        raise

if __name__ == "__main__":
    migrate_cohort_specific_tables()