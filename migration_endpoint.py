from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
import sqlite3
import os

router = APIRouter()

@router.post("/admin/migrate-cohort-courses")
async def migrate_cohort_courses(db: Session = Depends(get_db)):
    """
    Migration endpoint to add is_cohort_specific column to cohort_courses table
    """
    try:
        # Close the current session to avoid conflicts
        db.close()
        
        # Connect directly to SQLite
        conn = sqlite3.connect("lms.db")
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(cohort_courses)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_cohort_specific' not in columns:
            # Add the new column
            cursor.execute("""
                ALTER TABLE cohort_courses 
                ADD COLUMN is_cohort_specific BOOLEAN DEFAULT 0
            """)
            
            # Update existing records
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
            conn.close()
            
            return {
                "message": "Migration completed successfully",
                "details": "Added is_cohort_specific column and updated existing data"
            }
        else:
            conn.close()
            return {
                "message": "Migration not needed",
                "details": "Column is_cohort_specific already exists"
            }
            
    except Exception as e:
        return HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")