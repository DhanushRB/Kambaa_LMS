import requests
import time
from database import SessionLocal, User
from auth import create_access_token_with_session, get_password_hash

BASE_URL = "http://localhost:8000/api"

def setup_test_user():
    db = SessionLocal()
    # Create a fresh test student
    test_email = "test_student_restricted@example.com"
    user = db.query(User).filter(User.email == test_email).first()
    if user:
        db.delete(user)
        db.commit()
    
    new_user = User(
        username="teststudent",
        email=test_email,
        password_hash=get_password_hash("password123"),
        role="Student",
        user_type="Student",
        college="Test College",
        department="Test Dept",
        year="1"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    db.close()
    return test_email, "password123"

def test_multi_login():
    email, password = setup_test_user()
    print(f"Test user created: {email}")

    # 1. Login Session A
    print("\n[Step 1] Logging in as Session A...")
    resp_a = requests.post(f"{BASE_URL}/student/login", json={"username": email, "password": password})
    assert resp_a.status_code == 200
    token_a = resp_a.json()["access_token"]
    print(f"Session A token acquired: {token_a[:30]}...")

    # Verify Session A works
    headers_a = {"Authorization": f"Bearer {token_a}"}
    verify_a = requests.get(f"{BASE_URL}/student/login-page", headers=headers_a) # Using a simple endpoint for test
    # Note: student/login-page doesn't require auth in router but we test middleware by calling a protected one
    
    # Let's use an endpoint that requires auth
    verify_a = requests.get(f"{BASE_URL}/calendar/events", headers=headers_a)
    print(f"Session A initial test: {verify_a.status_code}")
    assert verify_a.status_code == 200

    # 2. Login Session B (Should invalidate Session A)
    print("\n[Step 2] Logging in as Session B (should invalidate A)...")
    resp_b = requests.post(f"{BASE_URL}/student/login", json={"username": email, "password": password})
    assert resp_b.status_code == 200
    token_b = resp_b.json()["access_token"]
    print(f"Session B token acquired: {token_b[:30]}...")

    # 3. Verify Session A is now invalid
    print("\n[Step 3] Verifying Session A is now invalid...")
    verify_a_retest = requests.get(f"{BASE_URL}/calendar/events", headers=headers_a)
    print(f"Session A retest (expected 401): {verify_a_retest.status_code}")
    if verify_a_retest.status_code == 401:
        print("SUCCESS: Session A was correctly invalidated.")
        print(f"Detail: {verify_a_retest.json()}")
    else:
        print("FAILURE: Session A is still valid!")
        assert verify_a_retest.status_code == 401

    # 4. Verify Session B is still valid
    print("\n[Step 4] Verifying Session B is still valid...")
    headers_b = {"Authorization": f"Bearer {token_b}"}
    verify_b = requests.get(f"{BASE_URL}/calendar/events", headers=headers_b)
    print(f"Session B test: {verify_b.status_code}")
    assert verify_b.status_code == 200
    print("SUCCESS: Session B is valid.")

    # 5. Test Logout for Session B
    print("\n[Step 5] Logging out Session B...")
    logout_b = requests.post(f"{BASE_URL}/student/logout", headers=headers_b)
    print(f"Logout response: {logout_b.status_code}")
    assert logout_b.status_code == 200

    # 6. Verify Session B is now invalid
    print("\n[Step 6] Verifying Session B is invalid after logout...")
    verify_b_retest = requests.get(f"{BASE_URL}/calendar/events", headers=headers_b)
    print(f"Session B retest after logout (expected 401): {verify_b_retest.status_code}")
    if verify_b_retest.status_code == 401:
        print("SUCCESS: Session B was correctly invalidated after logout.")
    else:
        print("FAILURE: Session B is still valid after logout!")
        assert verify_b_retest.status_code == 401

if __name__ == "__main__":
    try:
        test_multi_login()
        print("\nALL TESTS PASSED!")
    except Exception as e:
        print(f"\nTESTS FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
