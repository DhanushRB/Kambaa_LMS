#!/usr/bin/env python3
"""
Test script to verify meeting links are being created and retrieved correctly
"""

import requests
import json
from datetime import datetime, timedelta

# Configuration
BASE_URL = "http://localhost:8000"  # Adjust if your backend runs on a different port
ADMIN_USERNAME = "admin"  # Replace with actual admin username
ADMIN_PASSWORD = "admin123"  # Replace with actual admin password

def login_admin():
    """Login as admin and get token"""
    login_data = {
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    }
    
    response = requests.post(f"{BASE_URL}/api/auth/admin/login", json=login_data)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"Login failed: {response.status_code} - {response.text}")
        return None

def test_create_meeting_link(token, session_id):
    """Test creating a meeting link"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test data
    meeting_data = {
        "session_id": session_id,
        "content_type": "MEETING_LINK",
        "title": "Test Meeting Link",
        "description": "This is a test meeting link",
        "meeting_url": "https://zoom.us/j/123456789",
        "scheduled_time": (datetime.now() + timedelta(days=1)).isoformat()
    }
    
    print(f"Creating meeting link for session {session_id}...")
    
    # Try cohort session content JSON endpoint
    response = requests.post(f"{BASE_URL}/api/admin/session-content-json", 
                           json=meeting_data, headers=headers)
    
    if response.status_code == 200:
        print("✓ Meeting link created successfully via cohort JSON endpoint")
        return response.json()["content_id"]
    else:
        print(f"✗ Cohort JSON endpoint failed: {response.status_code} - {response.text}")
    
    # Try enhanced session content endpoint
    response = requests.post(f"{BASE_URL}/api/session-content/create", 
                           json=meeting_data, headers=headers)
    
    if response.status_code == 200:
        print("✓ Meeting link created successfully via enhanced endpoint")
        return response.json()["content_id"]
    else:
        print(f"✗ Enhanced endpoint failed: {response.status_code} - {response.text}")
    
    # Try form-based cohort endpoint
    form_data = {
        "session_id": session_id,
        "content_type": "MEETING_LINK",
        "title": "Test Meeting Link",
        "description": "This is a test meeting link",
        "meeting_url": "https://zoom.us/j/123456789"
    }
    
    response = requests.post(f"{BASE_URL}/api/admin/session-content", 
                           data=form_data, headers=headers)
    
    if response.status_code == 200:
        print("✓ Meeting link created successfully via cohort form endpoint")
        return response.json()["content_id"]
    else:
        print(f"✗ Cohort form endpoint failed: {response.status_code} - {response.text}")
    
    return None

def test_retrieve_session_content(token, session_id):
    """Test retrieving session content"""
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"Retrieving content for session {session_id}...")
    
    response = requests.get(f"{BASE_URL}/api/sessions/{session_id}/content", headers=headers)
    
    if response.status_code == 200:
        content_data = response.json()
        contents = content_data.get("contents", [])
        
        print(f"✓ Retrieved {len(contents)} content items")
        
        meeting_links = [c for c in contents if c["content_type"] == "MEETING_LINK"]
        print(f"✓ Found {len(meeting_links)} meeting links")
        
        for meeting in meeting_links:
            print(f"  - {meeting['title']}: {meeting['meeting_url']}")
            print(f"    Source: {meeting.get('source', 'unknown')}")
            print(f"    Created: {meeting.get('created_at', 'unknown')}")
        
        return contents
    else:
        print(f"✗ Failed to retrieve content: {response.status_code} - {response.text}")
        return []

def main():
    """Main test function"""
    print("Testing Meeting Links Creation and Retrieval")
    print("=" * 50)
    
    # Login
    token = login_admin()
    if not token:
        print("Failed to login. Please check credentials.")
        return
    
    print("✓ Successfully logged in as admin")
    
    # Test with a sample session ID (you may need to adjust this)
    test_session_id = 1  # Replace with an actual session ID from your database
    
    # Test creating meeting link
    content_id = test_create_meeting_link(token, test_session_id)
    
    if content_id:
        print(f"✓ Meeting link created with ID: {content_id}")
    else:
        print("✗ Failed to create meeting link")
    
    # Test retrieving content
    contents = test_retrieve_session_content(token, test_session_id)
    
    if contents:
        print("✓ Content retrieval test passed")
    else:
        print("✗ Content retrieval test failed")
    
    print("\nTest completed!")

if __name__ == "__main__":
    main()