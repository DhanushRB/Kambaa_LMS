# Cohort Course Router - Register cohort-specific course endpoints

from fastapi import APIRouter
from cohort_course_endpoints import (
    create_cohort_course,
    get_cohort_courses,
    update_cohort_course,
    delete_cohort_course,
    check_cohort_access
)

router = APIRouter()

# Cohort-specific course management endpoints
router.post("/admin/cohorts/{cohort_id}/courses/create")(create_cohort_course)
router.get("/admin/cohorts/{cohort_id}/courses")(get_cohort_courses)
# Removed the problematic route: /admin/cohorts/{cohort_id}/courses/{course_id}
# This allows frontend to navigate directly to modules page
router.put("/admin/cohorts/{cohort_id}/courses/{course_id}")(update_cohort_course)
router.delete("/admin/cohorts/{cohort_id}/courses/{course_id}")(delete_cohort_course)
router.get("/admin/cohorts/{cohort_id}/access")(check_cohort_access)