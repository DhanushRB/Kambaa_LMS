import sys
import os

# Add backend to path
sys.path.append(r"D:\LMS-v2\backend")

from database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        print("Starting migration...")
        
        # Add columns if they don't exist
        columns_to_add = [
            ("first_join_time", "DATETIME"),
            ("last_leave_time", "DATETIME"),
            ("total_duration_minutes", "FLOAT DEFAULT 0.0"),
            ("updated_at", "DATETIME")
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                conn.execute(text(f"ALTER TABLE cohort_attendances ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                print(f"Added column: {col_name}")
            except Exception as e:
                # Likely already exists
                print(f"Skipping {col_name}: {str(e)}")
        
        print("Migration complete.")

if __name__ == "__main__":
    migrate()
