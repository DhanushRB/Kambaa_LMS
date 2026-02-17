import sys
import os

# Add backend to path
sys.path.append(r"D:\LMS-v2\backend")

from database import SessionLocal, User

def check_users():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print(f"Total Users: {len(users)}")
        for u in users[:20]:
            print(f"  - ID={u.id}, Username='{u.username}', Role='{u.role}', Email='{u.email}'")
    finally:
        db.close()

if __name__ == "__main__":
    check_users()
