
import requests
import json
from database import SessionLocal, Admin
from auth import create_access_token

API_URL = "http://localhost:8000/api"

def get_admin_token():
    # Direct token generation to bypass login form/hashing uncertainty
    db = SessionLocal()
    admin = db.query(Admin).first()
    if not admin:
        print("No admin found.")
        return None
    
    token = create_access_token(data={"sub": admin.username, "role": "Admin", "id": admin.id})
    db.close()
    return token

def test_api_assignment():
    token = get_admin_token()
    if not token:
        print("Failed to get token")
        return

    headers = {"Authorization": f"Bearer {token}"}
    
    # Get a course
    courses_resp = requests.get(f"{API_URL}/courses/", headers=headers)
    if courses_resp.status_code != 200:
        print(f"Failed to get courses: {courses_resp.text}")
        return
        
    courses = courses_resp.json().get("courses", [])
    if not courses:
        print("No courses found")
        return
        
    course_id = courses[0]['id']
    print(f"Testing with Course ID: {course_id}")
    
    # Payload mimicking Frontend
    payload = {
        "assignments": [{
            "assignment_type": "all",
            "user_id": None,
            "college": None
        }]
    }
    
    # Call PUT
    print(f"Sending payload: {json.dumps(payload)}")
    resp = requests.put(f"{API_URL}/courses/{course_id}", json=payload, headers=headers)
    
    print(f"Response Status: {resp.status_code}")
    print(f"Response Body: {resp.text}")

if __name__ == "__main__":
    test_api_assignment()
