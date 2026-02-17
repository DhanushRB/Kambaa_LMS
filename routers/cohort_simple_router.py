from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db, Cohort, UserCohort, User, PresenterCohort, Presenter, Mentor, Admin
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["cohort_simple"])

@router.get("/cohorts")
async def get_cohorts_simple(db: Session = Depends(get_db)):
    """Simple cohorts endpoint that works without auth"""
    try:
        cohorts = db.query(Cohort).filter(Cohort.is_active == True).all()
        
        cohorts_data = []
        for cohort in cohorts:
            user_count = db.query(UserCohort).filter(
                UserCohort.cohort_id == cohort.id,
                UserCohort.is_active == True
            ).count()
            
            cohorts_data.append({
                "id": cohort.id,
                "name": cohort.name,
                "description": cohort.description or "",
                "user_count": user_count,
                "is_active": cohort.is_active
            })
        
        return {"cohorts": cohorts_data}
        
    except Exception as e:
        logger.error(f"Get cohorts error: {str(e)}")
        return {"cohorts": []}

@router.get("/cohorts/{cohort_id}/members")
async def get_cohort_members_simple(cohort_id: int, db: Session = Depends(get_db)):
    """Simple cohort members endpoint without auth"""
    try:
        members = []
        
        user_cohorts = db.query(UserCohort).filter(
            UserCohort.cohort_id == cohort_id,
            UserCohort.is_active == True
        ).all()
        
        for uc in user_cohorts:
            user = db.query(User).filter(User.id == uc.user_id).first()
            if user:
                members.append({
                    "id": user.id,
                    "name": user.username,
                    "email": user.email,
                    "role": "Student",
                    "user_type": "Student"
                })
        
        return {"members": members}
        
    except Exception as e:
        logger.error(f"Get cohort members error: {str(e)}")
        return {"members": []}

@router.get("/cohorts/{cohort_id}/users")
async def get_cohort_users_simple(cohort_id: int, db: Session = Depends(get_db)):
    """Simple cohort users endpoint without auth"""
    try:
        from database import MentorCohort
        
        users = []
        
        # Get students in cohort
        user_cohorts = db.query(UserCohort).filter(
            UserCohort.cohort_id == cohort_id,
            UserCohort.is_active == True
        ).all()
        
        for uc in user_cohorts:
            user = db.query(User).filter(User.id == uc.user_id).first()
            if user:
                users.append({
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": "Student",
                    "user_type": "Student",
                    "college": user.college,
                    "department": user.department
                })
        
        # Get presenters assigned to cohort
        presenter_cohorts = db.query(PresenterCohort).filter(
            PresenterCohort.cohort_id == cohort_id
        ).all()
        
        for pc in presenter_cohorts:
            presenter = db.query(Presenter).filter(Presenter.id == pc.presenter_id).first()
            if presenter:
                users.append({
                    "id": presenter.id,
                    "username": presenter.username,
                    "email": presenter.email,
                    "role": "Presenter",
                    "user_type": "Presenter"
                })
        
        # Get mentors assigned to this specific cohort
        mentor_cohorts = db.query(MentorCohort).filter(
            MentorCohort.cohort_id == cohort_id
        ).all()
        
        for mc in mentor_cohorts:
            mentor = db.query(Mentor).filter(Mentor.id == mc.mentor_id).first()
            if mentor:
                users.append({
                    "id": mentor.id,
                    "username": mentor.username,
                    "email": mentor.email,
                    "role": "Mentor",
                    "user_type": "Mentor"
                })
        
        # Add all admins (always visible)
        admins = db.query(Admin).all()
        for admin in admins:
            users.append({
                "id": admin.id,
                "username": admin.username,
                "email": admin.email,
                "role": "Admin",
                "user_type": "Admin"
            })
        
        # Add all managers (always visible)
        managers = db.query(Manager).all()
        for manager in managers:
            users.append({
                "id": manager.id,
                "username": manager.username,
                "email": manager.email,
                "role": "Manager",
                "user_type": "Manager"
            })
        
        return {"users": users}
        
    except Exception as e:
        logger.error(f"Get cohort users error: {str(e)}")
        return {"users": []}

@router.get("/cohorts/{cohort_id}/staff")
async def get_cohort_staff_simple(cohort_id: int, db: Session = Depends(get_db)):
    """Simple cohort staff endpoint without auth"""
    try:
        from database import MentorCohort
        
        staff = []
        
        # Get presenters assigned to cohort
        presenter_cohorts = db.query(PresenterCohort).filter(
            PresenterCohort.cohort_id == cohort_id
        ).all()
        
        for pc in presenter_cohorts:
            presenter = db.query(Presenter).filter(Presenter.id == pc.presenter_id).first()
            if presenter:
                staff.append({
                    "id": presenter.id,
                    "username": presenter.username,
                    "email": presenter.email,
                    "role": "Presenter",
                    "user_type": "Presenter"
                })
        
        # Get mentors assigned to this specific cohort
        mentor_cohorts = db.query(MentorCohort).filter(
            MentorCohort.cohort_id == cohort_id
        ).all()
        
        for mc in mentor_cohorts:
            mentor = db.query(Mentor).filter(Mentor.id == mc.mentor_id).first()
            if mentor:
                staff.append({
                    "id": mentor.id,
                    "username": mentor.username,
                    "email": mentor.email,
                    "role": "Mentor",
                    "user_type": "Mentor"
                })
        
        # Add all admins (always visible)
        admins = db.query(Admin).all()
        for admin in admins:
            staff.append({
                "id": admin.id,
                "username": admin.username,
                "email": admin.email,
                "role": "Admin",
                "user_type": "Admin"
            })
        
        # Add all managers (always visible)
        managers = db.query(Manager).all()
        for manager in managers:
            staff.append({
                "id": manager.id,
                "username": manager.username,
                "email": manager.email,
                "role": "Manager",
                "user_type": "Manager"
            })
        
        return {"staff": staff}
        
    except Exception as e:
        logger.error(f"Get cohort staff error: {str(e)}")
        return {"staff": []}

@router.get("/cohorts/{cohort_id}/presenters")
async def get_cohort_presenters_simple(cohort_id: int, db: Session = Depends(get_db)):
    """Simple cohort presenters endpoint without auth"""
    try:
        presenters = []
        
        presenter_cohorts = db.query(PresenterCohort).filter(
            PresenterCohort.cohort_id == cohort_id
        ).all()
        
        for pc in presenter_cohorts:
            presenter = db.query(Presenter).filter(Presenter.id == pc.presenter_id).first()
            if presenter:
                presenters.append({
                    "id": presenter.id,
                    "username": presenter.username,
                    "email": presenter.email,
                    "role": "Presenter",
                    "user_type": "Presenter"
                })
        
        return {"presenters": presenters}
        
    except Exception as e:
        logger.error(f"Get cohort presenters error: {str(e)}")
        return {"presenters": []}

@router.get("/student/cohort")
async def get_student_cohort(db: Session = Depends(get_db)):
    """Get the student's assigned cohort - requires authentication via token"""
    try:
        from auth import verify_token
        from fastapi import Header
        
        # This endpoint should be called with Authorization header
        # For now, we'll make it work without strict auth to match the pattern of other endpoints
        # The frontend will need to pass the user_id or we can get it from token
        
        # Since this is in cohort_simple_router which doesn't use auth,
        # we'll return None and let the frontend handle it
        # This is a placeholder - the actual implementation should use proper auth
        
        return {
            "cohort": None,
            "message": "Please use the authenticated endpoint"
        }
        
    except Exception as e:
        logger.error(f"Get student cohort error: {str(e)}")
        return {"cohort": None}