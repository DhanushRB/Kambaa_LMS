#!/usr/bin/env python3
"""
Database migration script to create cohort_session_contents table
"""

import sqlite3
import os
from pathlib import Path

def migrate_database():
    """Create the cohort_session_contents table"""
    
    # Database path
    db_path = Path("lms.db")
    
    if not db_path.exists():
        print("Database file not found!")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='cohort_session_contents'
        """)
        
        if cursor.fetchone():
            print("Table 'cohort_session_contents' already exists!")
            conn.close()
            return True
        
        # Create the table
        cursor.execute("""
            CREATE TABLE cohort_session_contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                content_type VARCHAR(50),
                title VARCHAR(200),
                description TEXT,
                file_path VARCHAR(500),
                file_type VARCHAR(50),
                file_size INTEGER,
                meeting_url VARCHAR(500),
                scheduled_time DATETIME,
                uploaded_by INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES cohort_course_sessions(id),
                FOREIGN KEY (uploaded_by) REFERENCES admins(id)
            )
        """)
        
        conn.commit()
        print("Successfully created 'cohort_session_contents' table!")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("Running database migration...")
    success = migrate_database()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")