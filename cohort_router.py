# Cohort Router - Properly register cohort endpoints

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db, CohortCourse
from auth import get_current_admin_or_presenter
import logging

logger = logging.getLogger(__name__)
from cohort_endpoints import (
    create_cohort,
    get_cohorts,
    get_cohort_details,
    update_cohort,
    delete_cohort,
    add_users_to_cohort,
    remove_user_from_cohort,
    assign_courses_to_cohort,
    remove_course_from_cohort,
    get_available_users,
    get_available_courses,
    export_cohort_users
)

router = APIRouter()

# Register all cohort endpoints
router.post("/admin/cohorts")(create_cohort)
router.get("/admin/cohorts")(get_cohorts)
router.get("/admin/cohorts/{cohort_id}")(get_cohort_details)
router.put("/admin/cohorts/{cohort_id}")(update_cohort)
router.delete("/admin/cohorts/{cohort_id}")(delete_cohort)
router.post("/admin/cohorts/{cohort_id}/users")(add_users_to_cohort)
router.delete("/admin/cohorts/{cohort_id}/users/{user_id}")(remove_user_from_cohort)
router.post("/admin/cohorts/{cohort_id}/courses")(assign_courses_to_cohort)
router.delete("/admin/cohorts/{cohort_id}/courses/{course_id}")(remove_course_from_cohort)
router.get("/admin/available-users")(get_available_users)
router.get("/admin/available-courses")(get_available_courses)
router.get("/admin/cohorts/{cohort_id}/export")(export_cohort_users)

# Add routes without /admin prefix for compatibility
@router.delete("/cohorts/{cohort_id}/courses/{course_id}")
async def remove_course_from_cohort_simple(
    cohort_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_or_presenter)
):
    try:
        from database import Enrollment
        from cohort_specific_models import CohortSpecificCourse, CohortSpecificEnrollment
        
        # First, try to find regular course assignment
        cohort_course = db.query(CohortCourse).filter(
            CohortCourse.cohort_id == cohort_id,
            CohortCourse.course_id == course_id
        ).first()
        
        # If not found, try cohort-specific course
        cohort_specific_course = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.cohort_id == cohort_id,
            CohortSpecificCourse.id == course_id
        ).first()
        
        if not cohort_course and not cohort_specific_course:
            raise HTTPException(status_code=404, detail="Course not assigned to cohort")
        
        if cohort_course:
            # Remove regular course assignment and enrollments
            db.query(Enrollment).filter(
                Enrollment.course_id == course_id,
                Enrollment.cohort_id == cohort_id
            ).delete()
            db.delete(cohort_course)
            
        if cohort_specific_course:
            # 1. Delete enrollments FIRST (bulk, no ORM sync)
            db.query(CohortSpecificEnrollment)\
              .filter(CohortSpecificEnrollment.course_id == course_id)\
              .delete(synchronize_session=False)
            
            # 2. Flush to enforce delete order
            db.flush()
            
            # 3. Delete the course WITHOUT loading relationships
            db.query(CohortSpecificCourse)\
              .filter(CohortSpecificCourse.id == course_id)\
              .delete(synchronize_session=False)
        
        db.commit()
        return {"message": "Course removed from cohort successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to remove course from cohort: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to remove course from cohort: {str(e)}")