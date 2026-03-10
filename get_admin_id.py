
from database import get_db, Admin
from sqlalchemy.orm import Session

def get_admin():
    db = next(get_db())
    admin = db.query(Admin).first()
    if admin:
        print(f"Admin found: ID={admin.id}, Username={admin.username}")
    else:
        print("No admin found in database.")

if __name__ == "__main__":
    get_admin()
