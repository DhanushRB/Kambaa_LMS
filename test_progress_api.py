from fastapi.testclient import TestClient
from main import app
from database import get_db, User, Session as SessionModel, StudentSessionStatus
from auth import create_access_token

client = TestClient(app)

def test_progress_flow():
    # 1. Get a student user
    db = next(get_db())
    student = db.query(User).filter(User.user_type == "Student").first()
    
    if not student:
        print("No student found, skipping test")
        return

    print(f"Testing with student: {student.username} ({student.id})")
    
    # Generate token
    token = create_access_token({"sub": student.username, "id": student.id, "role": student.role, "type": "Student"})
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Find a session to test with
    session = db.query(SessionModel).first()
    if not session:
        print("No session found, skipping test")
        return
        
    print(f"Testing with session: {session.id} - {session.title}")
    
    # Check if route exists
    found_route = False
    for route in app.routes:
        if hasattr(route, "path") and "student/session/{session_id}/start" in route.path:
            found_route = True
            print(f"Found route: {route.path}")
            break
    if not found_route:
        print("WARNING: Route /student/session/{session_id}/start NOT FOUND in app.routes!")
        # Print all routes to help debug
        # for r in app.routes:
        #     if hasattr(r, "path"): print(r.path)
    
    # 3. Reset status for this session if exists
    db.query(StudentSessionStatus).filter(
        StudentSessionStatus.student_id == student.id,
        StudentSessionStatus.session_id == session.id
    ).delete()
    db.commit()
    
    # 5. Call Start Session endpoint
    print(f"Calling POST /api/student/session/{session.id}/start")
    response = client.post(f"/api/student/session/{session.id}/start", headers=headers)
    print(f"Start Session Response: {response.status_code} - {response.text}")
    
    if response.status_code != 200:
        print("Failed to start session")
        return

    # 6. Verify DB status
    db.expire_all() # Ensure we get fresh data
    status = db.query(StudentSessionStatus).filter(
        StudentSessionStatus.student_id == student.id,
        StudentSessionStatus.session_id == session.id
    ).first()
    
    if status:
        print(f"DB Status: {status.status}")
        assert status.status == "Started"
        print("Test Passed!")
    else:
        print("Test Failed: Status record not found in DB")
        all_recs = db.query(StudentSessionStatus).all()
        print(f"Total records in DB: {len(all_recs)}")
        for r in all_recs:
             print(f"Record: student={r.student_id}, session={r.session_id}, status={r.status}")

if __name__ == "__main__":
    try:
        test_progress_flow()
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback
        traceback.print_exc()
