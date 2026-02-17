import sys
import os
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime

# Add the current directory to sys.path to import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from database import get_db, User, SessionLocal
from cohort_specific_models import CohortSessionContent
from resource_analytics_models import ResourceView
from auth import create_access_token

client = TestClient(app)

def test_cohort_resource_tracking():
    print("\n--- Testing Cohort Resource Tracking ---")
    db = SessionLocal()
    
    try:
        # 1. Get a student user
        student = db.query(User).filter(User.role == "Student").first()
        if not student:
            print("No student found in database. Skipping test.")
            return

        print(f"Using student: {student.username} (ID: {student.id})")
        
        # 2. Get a cohort resource
        cohort_resource = db.query(CohortSessionContent).filter(
            CohortSessionContent.content_type == "RESOURCE"
        ).first()
        
        if not cohort_resource:
            print("No cohort resource found in database. Please ensure a cohort course with resources exists.")
            return
            
        print(f"Using cohort resource: {cohort_resource.title} (ID: {cohort_resource.id})")
        
        # Ensure the file path exists 
        if not os.path.exists(cohort_resource.file_path):
            print(f"Warning: File path {cohort_resource.file_path} doesn't exist. Creating a dummy file.")
            os.makedirs(os.path.dirname(cohort_resource.file_path), exist_ok=True)
            with open(cohort_resource.file_path, "w") as f:
                f.write("test content")

        # 3. Generate token
        token = create_access_token({
            "sub": student.username,
            "user_id": student.id,
            "role": "Student"
        })
        headers = {"Authorization": f"Bearer {token}"}
        
        # 4. Record current count of views
        initial_views = db.query(ResourceView).filter(
            ResourceView.resource_id == cohort_resource.id,
            ResourceView.student_id == student.id,
            ResourceView.resource_type == "COHORT_RESOURCE"
        ).count()
        print(f"Initial view count in DB: {initial_views}")
        
        # 5. Call the view endpoint
        print(f"Calling GET /api/admin/cohort-content/{cohort_resource.id}/view")
        response = client.get(f"/api/admin/cohort-content/{cohort_resource.id}/view", headers=headers)
        
        print(f"Response status: {response.status_code}")
        if response.status_code != 200:
            print(f"Error Response: {response.text}")
            
        # 6. Verify view was tracked using a FRESH session to avoid caching
        db.close()
        db = SessionLocal()
        
        final_views = db.query(ResourceView).filter(
            ResourceView.resource_id == cohort_resource.id,
            ResourceView.student_id == student.id,
            ResourceView.resource_type == "COHORT_RESOURCE"
        ).count()
        
        print(f"Final view count in DB: {final_views}")
        
        if final_views > initial_views:
            print("SUCCESS: Cohort resource view was tracked correctly!")
        else:
            print("FAILURE: View count did not increase.")
            # Let's see ALL views for this student to see if anything was recorded with different parameters
            all_student_views = db.query(ResourceView).filter(ResourceView.student_id == student.id).all()
            print(f"Total views for this student: {len(all_student_views)}")
            for v in all_student_views:
                print(f"  - Resource ID: {v.resource_id}, Type: {v.resource_type}, Time: {v.viewed_at}")
            
            assert False, "View tracking failed"

    finally:
        db.close()

if __name__ == "__main__":
    test_cohort_resource_tracking()
