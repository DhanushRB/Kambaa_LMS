from sqlalchemy import create_engine, inspect
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

inspector = inspect(engine)

def check_table(table_name):
    print(f"\n--- TABLE: {table_name} ---")
    columns = inspector.get_columns(table_name)
    for column in columns:
        print(f"Column: {column['name']}, Type: {column['type']}")

check_table("users")
check_table("cohorts")
check_table("enrollments")

# Sample data from users
from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)
session = Session()

from sqlalchemy import text
print("\n--- SAMPLE DATA FROM USERS ---")
try:
    result = session.execute(text("SELECT * FROM users LIMIT 5"))
    columns = result.keys()
    for row in result:
        print(dict(zip(columns, row)))
except Exception as e:
    print(f"Error query users: {e}")

session.close()
