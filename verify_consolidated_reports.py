
import requests
import json
import sys

BASE_URL = "http://localhost:8000/api"

def test_consolidated_reports():
    print("--- Verifying Consolidated User Reports Endpoint ---")
    
    # Login as Admin
    admin_login = {
        "username": "admin",
        "password": "password123"
    }
    resp = requests.post(f"{BASE_URL}/auth/admin/login", json=admin_login)
    
    if resp.status_code != 200:
        print(f"Admin login failed: {resp.text}")
        return

    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Fetch consolidated stats
    print("Fetching consolidated stats...")
    resp = requests.get(f"{BASE_URL}/admin/user-reports/consolidated?limit=5", headers=headers)
    
    if resp.status_code == 200:
        data = resp.json()
        users = data.get("users", [])
        total = data.get("total", 0)
        
        print(f"SUCCESS: Retrieved stats for {len(users)} users (Total: {total})")
        
        if len(users) > 0:
            print("\nSample User Stats:")
            user = users[0]
            print(json.dumps(user, indent=2))
            
            # Check for required fields
            required_fields = ["id", "username", "activities_count", "assignments_submitted", "quizzes_attempted", "attendance_rate"]
            missing = [f for f in required_fields if f not in user]
            if missing:
                print(f"WARNING: Missing fields in response: {missing}")
            else:
                print("All required fields are present.")
        else:
            print("No users found to verify structure.")
            
    else:
        print(f"FAILED to fetch consolidated stats: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    test_consolidated_reports()
