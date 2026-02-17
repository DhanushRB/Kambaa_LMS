import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found in .env")
    exit(1)

engine = create_engine(DATABASE_URL)

def migrate():
    try:
        with engine.connect() as connection:
            print("Starting comprehensive migration...")
            
            # Courses Table
            print("Updating 'courses' table...")
            columns_to_add = [
                ("approval_status", "VARCHAR(20) DEFAULT 'approved'"),
                ("payment_type", "VARCHAR(20) DEFAULT 'free'"),
                ("default_price", "FLOAT DEFAULT 0.0")
            ]
            for col_name, col_type in columns_to_add:
                result = connection.execute(text(f"SHOW COLUMNS FROM courses LIKE '{col_name}'"))
                if not result.fetchone():
                    print(f"Adding '{col_name}' to 'courses'...")
                    connection.execute(text(f"ALTER TABLE courses ADD COLUMN {col_name} {col_type}"))
                    print(f"'{col_name}' added.")
            
            # Enrollments Table
            print("\nUpdating 'enrollments' table...")
            enrollment_cols = [
                ("payment_status", "VARCHAR(20) DEFAULT 'not_required'"),
                ("payment_amount", "FLOAT DEFAULT 0.0")
            ]
            for col_name, col_type in enrollment_cols:
                result = connection.execute(text(f"SHOW COLUMNS FROM enrollments LIKE '{col_name}'"))
                if not result.fetchone():
                    print(f"Adding '{col_name}' to 'enrollments'...")
                    connection.execute(text(f"ALTER TABLE enrollments ADD COLUMN {col_name} {col_type}"))
                    print(f"'{col_name}' added.")

            # Course Assignments Table
            print("\nUpdating 'course_assignments' table...")
            assignment_cols = [
                ("assignment_mode", "VARCHAR(20) DEFAULT 'free'"),
                ("amount", "FLOAT DEFAULT 0.0")
            ]
            for col_name, col_type in assignment_cols:
                result = connection.execute(text(f"SHOW COLUMNS FROM course_assignments LIKE '{col_name}'"))
                if not result.fetchone():
                    print(f"Adding '{col_name}' to 'course_assignments'...")
                    connection.execute(text(f"ALTER TABLE course_assignments ADD COLUMN {col_name} {col_type}"))
                    print(f"'{col_name}' added.")

            connection.commit()
            print("\nMigration completed successfully.")
            
    except Exception as e:
        print(f"\nMigration error: {str(e)}")

if __name__ == "__main__":
    migrate()
