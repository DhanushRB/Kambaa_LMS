
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("DATABASE_URL")
print(f"URL: {url}")
engine = create_engine(url)
with engine.connect() as conn:
    print("--- COLUMNS ---")
    res = conn.execute(text("SHOW COLUMNS FROM courses"))
    for row in res:
        print(row)
    
    print("\n--- TEST QUERY ---")
    try:
        res = conn.execute(text("SELECT id, approval_status FROM courses LIMIT 1"))
        print("Success!")
    except Exception as e:
        print(f"Error: {e}")
