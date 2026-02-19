from database import engine
from sqlalchemy import text

def run_migration():
    with engine.connect() as conn:
        print("Starting database migration...")
        
        # Add banner_image to courses table
        try:
            conn.execute(text("ALTER TABLE courses ADD COLUMN banner_image VARCHAR(500) NULL"))
            conn.commit()
            print("Successfully added banner_image to 'courses' table.")
        except Exception as e:
            if "Duplicate column name" in str(e):
                print("Column 'banner_image' already exists in 'courses' table.")
            else:
                print(f"Error updating 'courses' table: {e}")
        
        # Add banner_image to cohort_specific_courses table
        try:
            conn.execute(text("ALTER TABLE cohort_specific_courses ADD COLUMN banner_image VARCHAR(500) NULL"))
            conn.commit()
            print("Successfully added banner_image to 'cohort_specific_courses' table.")
        except Exception as e:
            if "Duplicate column name" in str(e):
                print("Column 'banner_image' already exists in 'cohort_specific_courses' table.")
            else:
                print(f"Error updating 'cohort_specific_courses' table: {e}")
                
        print("Migration completed.")

if __name__ == "__main__":
    run_migration()
