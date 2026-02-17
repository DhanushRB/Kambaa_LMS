
import requests
import json
from database import SessionLocal, User
from auth import create_access_token

API_URL = "http://localhost:8000/api"

def get_student_token():
    db = SessionLocal()
    # Find a test student
    student = db.query(User).filter(User.role == 'Student').first()
    if not student:
        print("No student found.")
        return None
    
    print(f"Testing as Student: {student.username} (ID: {student.id})")
    token = create_access_token(data={"sub": student.username, "role": "Student", "id": student.id})
    db.close()
    return token

def test_student_courses():
    token = get_student_token()
    if not token:
        print("Failed to get token")
        return

    headers = {"Authorization": f"Bearer {token}"}
    
    # Get courses
    print("Calling GET /student/courses...")
    resp = requests.get(f"{API_URL}/student/courses", headers=headers)
    
    print(f"Response Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        courses = data.get("courses", [])
        print(f"Courses Found: {len(courses)}")
        for c in courses:
            print(f" - ID: {c.get('id')}, Title: {c.get('title')}")
    else:
        print(f"Error: {resp.text}")

if __name__ == "__main__":
    test_student_courses()
