"""
Database Migration Script: Add is_cohort_specific column to cohort_courses table

This script adds the is_cohort_specific column to distinguish between:
1. Courses created specifically for cohorts (is_cohort_specific=True)
2. Global courses assigned to cohorts (is_cohort_specific=False)

Run this script once to update your existing database.
"""

import sqlite3
import os

def migrate_database():
    db_path = "lms.db"
    
    if not os.path.exists(db_path):
        print("Database file not found. Creating new database with updated schema.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(cohort_courses)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_cohort_specific' not in columns:
            print("Adding is_cohort_specific column to cohort_courses table...")
            
            # Add the new column with default value False
            cursor.execute("""
                ALTER TABLE cohort_courses 
                ADD COLUMN is_cohort_specific BOOLEAN DEFAULT 0
            """)
            
            # Update existing records: set is_cohort_specific=True for courses that are only in one cohort
            # This is a best-guess migration for existing data
            cursor.execute("""
                UPDATE cohort_courses 
                SET is_cohort_specific = 1 
                WHERE course_id IN (
                    SELECT course_id 
                    FROM cohort_courses 
                    GROUP BY course_id 
                    HAVING COUNT(*) = 1
                )
            """)
            
            conn.commit()
            print("Migration completed successfully!")
            print("- Added is_cohort_specific column")
            print("- Updated existing single-cohort courses as cohort-specific")
            
        else:
            print("Column is_cohort_specific already exists. No migration needed.")
            
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()