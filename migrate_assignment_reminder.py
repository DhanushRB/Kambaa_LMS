from database import engine
from sqlalchemy import text

def migrate():
    print("Running migration to add due_reminder_sent to assignments...")
    try:
        with engine.connect() as connection:
            # Check if column exists first
            result = connection.execute(text("SHOW COLUMNS FROM assignments LIKE 'due_reminder_sent'"))
            column_exists = result.fetchone() is not None
            
            if not column_exists:
                connection.execute(text("ALTER TABLE assignments ADD COLUMN due_reminder_sent BOOLEAN DEFAULT FALSE"))
                connection.commit()
                print("Column 'due_reminder_sent' added successfully!")
            else:
                print("Column 'due_reminder_sent' already exists.")
    except Exception as e:
        print(f"Migration error: {str(e)}")

if __name__ == "__main__":
    migrate()
