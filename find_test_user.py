from database import SessionLocal, User
db = SessionLocal()
user = db.query(User).filter(User.role == "Student").first()
if user:
    print(f"ID: {user.id}, Username: {user.username}, Email: {user.email}")
else:
    print("No student found")
db.close()
