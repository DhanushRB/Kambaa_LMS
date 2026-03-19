import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

def migrate():
    # Database connection parameters from environment or defaults
    db_host = os.getenv("DB_HOST", "localhost")
    db_user = os.getenv("DB_USER", "root")
    db_password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "database_db")

    try:
        connection = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            cursorclass=pymysql.cursors.DictCursor
        )
        with connection.cursor() as cursor:
            # Update submission_type enum for assignments table
            print("Updating submission_type enum in assignments table...")
            cursor.execute("ALTER TABLE assignments MODIFY COLUMN submission_type ENUM('FILE', 'TEXT', 'LINK', 'BOTH') DEFAULT 'FILE'")
            
            print("Migration successful!")
            connection.commit()
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        if 'connection' in locals():
            connection.close()

if __name__ == "__main__":
    migrate()
