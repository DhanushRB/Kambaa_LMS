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
            print("Checking if 'approval_status' exists in 'courses' table...")
            # Check if column exists
            result = connection.execute(text("SHOW COLUMNS FROM courses LIKE 'approval_status'"))
            if not result.fetchone():
                print("Adding 'approval_status' column to 'courses' table...")
                connection.execute(text("ALTER TABLE courses ADD COLUMN approval_status VARCHAR(20) DEFAULT 'approved' AFTER is_active"))
                connection.commit()
                print("Column 'approval_status' added successfully.")
            else:
                print("Column 'approval_status' already exists.")
    except Exception as e:
        print(f"Migration error: {str(e)}")

if __name__ == "__main__":
    migrate()
