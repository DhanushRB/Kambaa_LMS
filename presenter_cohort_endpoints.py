from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db, Cohort, User, UserCohort, CohortCourse, Course, PresenterCohort, Presenter
from auth import get_current_presenter
from schemas import CohortUpdate, CohortUserAdd, CohortCourseAssign
from main import log_presenter_action
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Additional presenter endpoints for cohort management
@router.get("/presenter/cohorts/{cohort_id}")
async def get_presenter_cohort_details(
    cohort_id: int,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    try:
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Get users in cohort
        user_cohorts = db.query(UserCohort).filter(UserCohort.cohort_id == cohort_id).all()
        users = [{
            "id": uc.user.id,
            "username": uc.user.username,
            "email": uc.user.email,
            "college_name": uc.user.college,
            "assigned_at": uc.assigned_at
        } for uc in user_cohorts]
        
        # Get assigned presenters
        presenter_assignments = db.query(PresenterCohort).filter(
            PresenterCohort.cohort_id == cohort_id
        ).all()
        
        presenters = []
        for assignment in presenter_assignments:
            presenter = assignment.presenter
            presenters.append({
                "id": presenter.id,
                "username": presenter.username,
                "email": presenter.email,
                "assigned_at": assignment.assigned_at
            })
        
        # Get cohort courses
        cohort_courses = db.query(CohortCourse).filter(CohortCourse.cohort_id == cohort_id).all()
        courses = [{
            "id": cc.course.id,
            "title": cc.course.title,
            "description": cc.course.description,
            "duration_weeks": cc.course.duration_weeks,
            "assigned_at": cc.assigned_at
        } for cc in cohort_courses]
        
        return {
            "id": cohort.id,
            "name": cohort.name,
            "description": cohort.description,
            "start_date": cohort.start_date,
            "end_date": cohort.end_date,
            "instructor_name": cohort.instructor_name,
            "is_active": cohort.is_active,
            "created_at": cohort.created_at,
            "users": users,
            "courses": courses
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get presenter cohort details error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch cohort details")

@router.put("/presenter/cohorts/{cohort_id}")
async def update_presenter_cohort(
    cohort_id: int,
    cohort_data: CohortUpdate,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    try:
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        update_data = cohort_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(cohort, field, value)
        
        db.commit()
        
        # Log cohort update
        log_presenter_action(
            presenter_id=current_presenter.id,
            presenter_username=current_presenter.username,
            action_type="UPDATE",
            resource_type="COHORT",
            resource_id=cohort_id,
            details=f"Updated cohort: {cohort.name}"
        )
        
        return {"message": "Cohort updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update presenter cohort error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update cohort")

@router.delete("/presenter/cohorts/{cohort_id}")
async def delete_presenter_cohort(
    cohort_id: int,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    try:
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        cohort_name = cohort.name
        
        # Remove users from cohort
        db.query(UserCohort).filter(UserCohort.cohort_id == cohort_id).delete()
        
        # Remove course assignments
        db.query(CohortCourse).filter(CohortCourse.cohort_id == cohort_id).delete()
        
        # Update users' cohort_id to None
        db.query(User).filter(User.cohort_id == cohort_id).update({"cohort_id": None})
        
        db.delete(cohort)
        db.commit()
        
        # Log cohort deletion
        log_presenter_action(
            presenter_id=current_presenter.id,
            presenter_username=current_presenter.username,
            action_type="DELETE",
            resource_type="COHORT",
            resource_id=cohort_id,
            details=f"Deleted cohort: {cohort_name}"
        )
        
        return {"message": "Cohort deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete presenter cohort error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete cohort")

@router.post("/presenter/cohorts/{cohort_id}/users")
async def add_users_to_presenter_cohort(
    cohort_id: int,
    user_data: CohortUserAdd,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    try:
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        added_users = []
        errors = []
        
        for user_id in user_data.user_ids:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                errors.append(f"User ID {user_id} not found")
                continue
            
            # Check if user is already in a cohort
            existing_cohort = db.query(UserCohort).filter(UserCohort.user_id == user_id).first()
            if existing_cohort:
                errors.append(f"User {user.username} is already in cohort {existing_cohort.cohort.name}")
                continue
            
            # Add user to cohort
            user_cohort = UserCohort(
                user_id=user_id,
                cohort_id=cohort_id,
                assigned_by=current_presenter.id
            )
            db.add(user_cohort)
            
            # Update user's current cohort
            user.cohort_id = cohort_id
            
            added_users.append(user.username)
        
        db.commit()
        
        # Log cohort user addition
        if added_users:
            log_presenter_action(
                presenter_id=current_presenter.id,
                presenter_username=current_presenter.username,
                action_type="CREATE",
                resource_type="COHORT_USER",
                resource_id=cohort_id,
                details=f"Added {len(added_users)} users to cohort: {', '.join(added_users)}"
            )
        
        return {
            "message": f"Added {len(added_users)} users to cohort",
            "added_users": added_users,
            "errors": errors
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Add users to presenter cohort error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to add users to cohort")

@router.delete("/presenter/cohorts/{cohort_id}/users/{user_id}")
async def remove_user_from_presenter_cohort(
    cohort_id: int,
    user_id: int,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    try:
        user_cohort = db.query(UserCohort).filter(
            UserCohort.cohort_id == cohort_id,
            UserCohort.user_id == user_id
        ).first()
        
        if not user_cohort:
            raise HTTPException(status_code=404, detail="User not found in cohort")
        
        # Get user info for logging
        user = db.query(User).filter(User.id == user_id).first()
        username = user.username if user else f"User ID {user_id}"
        
        # Remove from cohort
        db.delete(user_cohort)
        
        # Update user's current cohort
        if user:
            user.cohort_id = None
        
        db.commit()
        
        # Log cohort user removal
        log_presenter_action(
            presenter_id=current_presenter.id,
            presenter_username=current_presenter.username,
            action_type="DELETE",
            resource_type="COHORT_USER",
            resource_id=cohort_id,
            details=f"Removed user {username} from cohort"
        )
        
        return {"message": "User removed from cohort successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Remove user from presenter cohort error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to remove user from cohort")

@router.post("/presenter/cohorts/{cohort_id}/courses")
async def assign_courses_to_presenter_cohort(
    cohort_id: int,
    course_data: CohortCourseAssign,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    try:
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        assigned_courses = []
        errors = []
        
        for course_id in course_data.course_ids:
            course = db.query(Course).filter(Course.id == course_id).first()
            if not course:
                errors.append(f"Course ID {course_id} not found")
                continue
            
            # Check if course is already assigned to cohort
            existing_assignment = db.query(CohortCourse).filter(
                CohortCourse.cohort_id == cohort_id,
                CohortCourse.course_id == course_id
            ).first()
            
            if existing_assignment:
                errors.append(f"Course {course.title} is already assigned to this cohort")
                continue
            
            # Assign course to cohort
            cohort_course = CohortCourse(
                cohort_id=cohort_id,
                course_id=course_id,
                assigned_by=current_presenter.id
            )
            db.add(cohort_course)
            assigned_courses.append(course.title)
        
        db.commit()
        
        # Log cohort course assignment
        if assigned_courses:
            log_presenter_action(
                presenter_id=current_presenter.id,
                presenter_username=current_presenter.username,
                action_type="CREATE",
                resource_type="COHORT_COURSE",
                resource_id=cohort_id,
                details=f"Assigned {len(assigned_courses)} courses to cohort: {', '.join(assigned_courses)}"
            )
        
        return {
            "message": f"Assigned {len(assigned_courses)} courses to cohort",
            "assigned_courses": assigned_courses,
            "errors": errors
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Assign courses to presenter cohort error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to assign courses to cohort")

@router.delete("/presenter/cohorts/{cohort_id}/courses/{course_id}")
async def remove_course_from_presenter_cohort(
    cohort_id: int,
    course_id: int,
    current_presenter: Presenter = Depends(get_current_presenter),
    db: Session = Depends(get_db)
):
    try:
        cohort_course = db.query(CohortCourse).filter(
            CohortCourse.cohort_id == cohort_id,
            CohortCourse.course_id == course_id
        ).first()
        
        if not cohort_course:
            raise HTTPException(status_code=404, detail="Course not assigned to cohort")
        
        # Get course info for logging
        course = db.query(Course).filter(Course.id == course_id).first()
        course_title = course.title if course else f"Course ID {course_id}"
        
        db.delete(cohort_course)
        db.commit()
        
        # Log cohort course removal
        log_presenter_action(
            presenter_id=current_presenter.id,
            presenter_username=current_presenter.username,
            action_type="DELETE",
            resource_type="COHORT_COURSE",
            resource_id=cohort_id,
            details=f"Removed course {course_title} from cohort"
        )
        
        return {"message": "Course removed from cohort successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Remove course from presenter cohort error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to remove course from cohort")