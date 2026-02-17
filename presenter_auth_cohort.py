# Presenter Authentication for Admin Endpoints Access
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db, Presenter
from auth import get_current_presenter

def get_presenter_for_admin_access(
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    """
    Authentication dependency for presenters to access admin endpoints.
    Returns presenter with admin-like permissions for management operations.
    """
    if not current_presenter:
        raise HTTPException(status_code=401, detail="Presenter authentication required")
    
    return current_presenter

# PRESENTER ACCESS TO ADMIN ENDPOINTS:

# COHORT MANAGEMENT:
# POST /admin/cohorts - Create cohort
# GET /admin/cohorts - List cohorts  
# GET /admin/cohorts/{cohort_id} - Get cohort details
# PUT /admin/cohorts/{cohort_id} - Update cohort
# DELETE /admin/cohorts/{cohort_id} - Delete cohort
# POST /admin/cohorts/{cohort_id}/users - Add users to cohort
# DELETE /admin/cohorts/{cohort_id}/users/{user_id} - Remove user from cohort
# POST /admin/cohorts/{cohort_id}/courses - Assign courses to cohort
# DELETE /admin/cohorts/{cohort_id}/courses/{course_id} - Remove course from cohort
# POST /admin/cohorts/{cohort_id}/bulk-upload - Bulk upload users to cohort

# USER MANAGEMENT:
# POST /admin/users - Create user
# GET /admin/users - List users (with pagination, search, filters)
# PUT /admin/users/{user_id} - Update user
# DELETE /admin/users/{user_id} - Delete user
# GET /admin/colleges - Get colleges list
# POST /admin/users/bulk-upload - Bulk upload users
# GET /admin/download-user-template - Download user template

# ANALYTICS & REPORTS:
# GET /admin/analytics/overview - System analytics overview
# GET /admin/reports/detailed - Detailed reports (attendance, progress, performance)
# GET /admin/certificates - List certificates
# POST /admin/certificates/generate - Generate certificate