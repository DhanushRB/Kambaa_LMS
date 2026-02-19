# Cohort Management Endpoints for Admin Dashboard

from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from database import get_db, Cohort, UserCohort, CohortCourse, User, Course, Admin, PresenterCohort, Presenter, Enrollment, MentorCohort, MentorCourse, MentorSession
from auth import get_current_admin_or_presenter
from datetime import datetime
from typing import List, Optional
from email_utils import send_course_added_notification
import csv
import io
import os
import logging

logger = logging.getLogger(__name__)

# Pydantic models for cohort management
from pydantic import BaseModel, Field

class CohortCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    start_date: datetime
    end_date: datetime
    instructor_name: Optional[str] = Field(None, max_length=200)

class CohortUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    instructor_name: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None

class CohortUserAdd(BaseModel):
    user_ids: List[int]

class CohortCourseAssign(BaseModel):
    course_ids: List[int]

# Cohort CRUD endpoints
async def create_cohort(
    cohort_data: CohortCreate,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        cohort = Cohort(
            name=cohort_data.name,
            description=cohort_data.description,
            start_date=cohort_data.start_date,
            end_date=cohort_data.end_date,
            instructor_name=cohort_data.instructor_name,
            created_by=current_admin.id
        )
        db.add(cohort)
        db.commit()
        db.refresh(cohort)
        
        return {
            "message": "Cohort created successfully",
            "cohort_id": cohort.id,
            "name": cohort.name
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create cohort: {str(e)}")

async def get_cohorts(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(Cohort)
        
        if search:
            query = query.filter(
                or_(
                    Cohort.name.contains(search),
                    Cohort.description.contains(search),
                    Cohort.instructor_name.contains(search)
                )
            )
        
        total = query.count()
        cohorts = query.offset((page - 1) * limit).limit(limit).all()
        
        result = []
        for cohort in cohorts:
            user_count = db.query(UserCohort).filter(UserCohort.cohort_id == cohort.id).count()
            
            # Count both global courses assigned to cohort and cohort-specific courses
            global_course_count = db.query(CohortCourse).filter(CohortCourse.cohort_id == cohort.id).count()
            
            # Import and count cohort-specific courses
            try:
                from cohort_specific_models import CohortSpecificCourse
                cohort_specific_count = db.query(CohortSpecificCourse).filter(
                    CohortSpecificCourse.cohort_id == cohort.id
                ).count()
            except ImportError:
                cohort_specific_count = 0
            
            total_course_count = global_course_count + cohort_specific_count
            
            result.append({
                "id": cohort.id,
                "name": cohort.name,
                "description": cohort.description,
                "start_date": cohort.start_date,
                "end_date": cohort.end_date,
                "instructor_name": cohort.instructor_name,
                "is_active": getattr(cohort, 'is_active', True),
                "user_count": user_count,
                "course_count": total_course_count,
                "created_at": cohort.created_at
            })
        
        return {
            "cohorts": result,
            "total": total,
            "page": page,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch cohorts: {str(e)}")

async def get_cohort_details(
    cohort_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Get users in cohort
        user_cohorts = db.query(UserCohort).filter(UserCohort.cohort_id == cohort_id).all()
        users = []
        for uc in user_cohorts:
            user = db.query(User).filter(User.id == uc.user_id).first()
            if user:
                users.append({
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "college_name": user.college,
                    "assigned_at": uc.assigned_at
                })
        
        # Get courses assigned to cohort (old system - global courses assigned to cohorts)
        cohort_courses = db.query(CohortCourse).filter(CohortCourse.cohort_id == cohort_id).all()
        courses = []
        for cc in cohort_courses:
            course = db.query(Course).filter(Course.id == cc.course_id).first()
            if course:
                courses.append({
                    "id": course.id,
                    "title": course.title,
                    "description": course.description,
                    "duration_weeks": course.duration_weeks,
                    "sessions_per_week": course.sessions_per_week,
                    "banner_image": course.banner_image,
                    "assigned_at": cc.assigned_at,
                    "is_cohort_specific": False
                })
        
        # Get cohort-specific courses (new system - courses created specifically for this cohort)
        from cohort_specific_models import CohortSpecificCourse, CohortCourseModule
        cohort_specific_courses = db.query(CohortSpecificCourse).filter(
            CohortSpecificCourse.cohort_id == cohort_id
        ).all()
        
        for course in cohort_specific_courses:
            modules_count = db.query(CohortCourseModule).filter(
                CohortCourseModule.course_id == course.id
            ).count()
            
            courses.append({
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "duration_weeks": course.duration_weeks,
                "sessions_per_week": course.sessions_per_week,
                "banner_image": course.banner_image,
                "modules_count": modules_count,
                "assigned_at": course.created_at,  # Use created_at as assigned_at for cohort-specific courses
                "is_cohort_specific": True
            })
        
        # Get assigned presenters
        from database import PresenterCohort
        presenter_assignments = db.query(PresenterCohort).filter(
            PresenterCohort.cohort_id == cohort_id
        ).all()
        
        presenters = []
        for assignment in presenter_assignments:
            presenter = db.query(Presenter).filter(Presenter.id == assignment.presenter_id).first()
            if presenter:
                presenters.append({
                    "id": presenter.id,
                    "username": presenter.username,
                    "email": presenter.email,
                    "assigned_at": assignment.assigned_at
                })
        
        return {
            "id": cohort.id,
            "name": cohort.name,
            "description": cohort.description,
            "start_date": cohort.start_date,
            "end_date": cohort.end_date,
            "instructor_name": cohort.instructor_name,
            "is_active": getattr(cohort, 'is_active', True),
            "created_at": cohort.created_at,
            "users": users,
            "courses": courses,
            "presenters": presenters
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch cohort details: {str(e)}")

async def update_cohort(
    cohort_id: int,
    cohort_data: CohortUpdate,
    current_admin = Depends(get_current_admin_or_presenter),
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
        return {"message": "Cohort updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update cohort: {str(e)}")

async def delete_cohort(
    cohort_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Delete all related records in the correct order to avoid foreign key constraints
        
        # 1. Delete enrollments that reference this cohort
        db.query(Enrollment).filter(Enrollment.cohort_id == cohort_id).delete()
        
        # 2. Delete mentor cohort assignments
        db.query(MentorCohort).filter(MentorCohort.cohort_id == cohort_id).delete()
        
        # 3. Delete mentor course assignments that reference this cohort
        db.query(MentorCourse).filter(MentorCourse.cohort_id == cohort_id).delete()
        
        # 4. Delete mentor session assignments that reference this cohort
        db.query(MentorSession).filter(MentorSession.cohort_id == cohort_id).delete()
        
        # 5. Delete presenter cohort assignments
        db.query(PresenterCohort).filter(PresenterCohort.cohort_id == cohort_id).delete()
        
        # 6. Remove users from cohort
        db.query(UserCohort).filter(UserCohort.cohort_id == cohort_id).delete()
        
        # 7. Remove course assignments
        db.query(CohortCourse).filter(CohortCourse.cohort_id == cohort_id).delete()
        
        # 8. Update users' cohort_id to None
        db.query(User).filter(User.cohort_id == cohort_id).update({"cohort_id": None})
        
        # 9. Finally delete the cohort
        db.delete(cohort)
        db.commit()
        
        return {"message": "Cohort deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete cohort: {str(e)}")

# User management endpoints
async def add_users_to_cohort(
    cohort_id: int,
    user_data: CohortUserAdd,
    current_admin = Depends(get_current_admin_or_presenter),
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
                assigned_by=current_admin.id
            )
            db.add(user_cohort)
            
            # Update user's current cohort
            user.cohort_id = cohort_id
            
            added_users.append(user.username)
            
            # Send welcome email using NotificationService (same as campaigns)
            try:
                from notification_service import NotificationService
                
                service = NotificationService(db)
                
                # Get template from database if available
                template_subject = "Welcome to Kamba LMS - Your Learning Journey Begins!"
                template_body = f"""
<p>Dear {user.username},</p>
<p>Welcome to Kamba LMS! We're excited to have you join our learning community.</p>
<p><strong>Your cohort details:</strong></p>
<ul>
    <li>Cohort Name: {cohort.name}</li>
    <li>Start Date: {cohort.start_date.strftime('%Y-%m-%d') if cohort.start_date else 'TBD'}</li>
    <li>Instructor: {cohort.instructor_name or 'TBD'}</li>
</ul>
<p><strong>What's next:</strong></p>
<ol>
    <li>Complete your profile setup</li>
    <li>Explore your course materials</li>
    <li>Join your first session</li>
    <li>Connect with your peers</li>
</ol>
<p>If you have any questions, don't hesitate to reach out to our support team.</p>
<p>Best regards,<br>The Kamba LMS Team</p>
<hr>
<p><small>This is an automated message. Please do not reply to this email.</small></p>
                """
                
                # Try to get custom template from database
                try:
                    from database import EmailTemplate
                    template = db.query(EmailTemplate).filter(
                        EmailTemplate.name == "Cohort Welcome Email",
                        EmailTemplate.is_active == True
                    ).first()
                    
                    if template:
                        template_subject = template.subject.format(
                            username=user.username,
                            cohort_name=cohort.name,
                            start_date=cohort.start_date.strftime('%Y-%m-%d') if cohort.start_date else 'TBD',
                            instructor_name=cohort.instructor_name or 'TBD'
                        )
                        # Convert plain text template to HTML with proper line breaks
                        template_body_raw = template.body.format(
                            username=user.username,
                            cohort_name=cohort.name,
                            start_date=cohort.start_date.strftime('%Y-%m-%d') if cohort.start_date else 'TBD',
                            instructor_name=cohort.instructor_name or 'TBD',
                            email=user.email
                        )
                        # Convert to HTML format
                        template_body = template_body_raw.replace('\n', '<br>').replace('\n\n', '<br><br>')
                except Exception as template_error:
                    print(f"Template formatting error, using default: {str(template_error)}")
                
                # Send using the same method as campaigns (this will retry on auth failure)
                email_log = service.send_email_notification(
                    user_id=user.id,
                    email=user.email,
                    subject=template_subject,
                    body=template_body
                )
                
                if email_log.status == "sent":
                    print(f"Cohort welcome email sent successfully to {user.email}")
                elif email_log.status == "queued":
                    print(f"Cohort welcome email queued for {user.email}")
                else:
                    print(f"Cohort welcome email failed for {user.email}: {email_log.error_message}")
                
            except Exception as e:
                print(f"Email send failed: {str(e)}")
                # Don't fail the user addition if email sending fails
        
        db.commit()
        
        return {
            "message": f"Added {len(added_users)} users to cohort",
            "added_users": added_users,
            "errors": errors
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add users to cohort: {str(e)}")

async def remove_user_from_cohort(
    cohort_id: int,
    user_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        user_cohort = db.query(UserCohort).filter(
            UserCohort.cohort_id == cohort_id,
            UserCohort.user_id == user_id
        ).first()
        
        if not user_cohort:
            raise HTTPException(status_code=404, detail="User not found in cohort")
        
        # Remove from cohort
        db.delete(user_cohort)
        
        # Update user's current cohort
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.cohort_id = None
        
        db.commit()
        return {"message": "User removed from cohort successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to remove user from cohort: {str(e)}")

# Course assignment endpoints
async def assign_courses_to_cohort(
    cohort_id: int,
    course_data: CohortCourseAssign,
    current_admin = Depends(get_current_admin_or_presenter),
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
                assigned_by=current_admin.id
            )
            db.add(cohort_course)
            assigned_courses.append(course.title)
            
            # Send email notification for this course
            await send_course_added_notification(
                db=db,
                cohort_id=cohort_id,
                course_title=course.title,
                course_description=course.description or "",
                duration_weeks=course.duration_weeks or 0,
                sessions_per_week=course.sessions_per_week or 0
            )
        
        db.commit()
        
        return {
            "message": f"Assigned {len(assigned_courses)} courses to cohort",
            "assigned_courses": assigned_courses,
            "errors": errors
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to assign courses to cohort: {str(e)}")

async def remove_course_from_cohort(
    cohort_id: int,
    course_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        cohort_course = db.query(CohortCourse).filter(
            CohortCourse.cohort_id == cohort_id,
            CohortCourse.course_id == course_id
        ).first()
        
        if not cohort_course:
            raise HTTPException(status_code=404, detail="Course not assigned to cohort")
        
        # Remove the course assignment
        db.delete(cohort_course)
        db.commit()
        
        return {"message": "Course removed from cohort successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to remove course from cohort: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to remove course from cohort: {str(e)}")

# Utility endpoints
async def get_available_users(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        # Get users who are not in any cohort and are students only
        users_in_cohorts = db.query(UserCohort.user_id)
        available_users = db.query(User).filter(
            ~User.id.in_(users_in_cohorts),
            User.user_type == "Student"  # Only show students
        ).all()
        
        return {
            "users": [{
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "college": user.college,
                "department": user.department,
                "year": user.year
            } for user in available_users]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch available users: {str(e)}")

async def get_available_courses(
    cohort_id: Optional[int] = None,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        if cohort_id:
            # Get courses not assigned to this specific cohort
            assigned_courses = db.query(CohortCourse.course_id).filter(
                CohortCourse.cohort_id == cohort_id
            ).subquery()
            available_courses = db.query(Course).filter(
                ~Course.id.in_(assigned_courses)
            ).all()
        else:
            # Get all courses
            available_courses = db.query(Course).all()
        
        return {
            "courses": [{
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "banner_image": course.banner_image,
                "duration_weeks": course.duration_weeks,
                "sessions_per_week": course.sessions_per_week,
                "is_active": course.is_active,
                "created_at": course.created_at
            } for course in available_courses]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch available courses: {str(e)}")

async def export_cohort_users(
    cohort_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Get users in cohort
        user_cohorts = db.query(UserCohort).filter(UserCohort.cohort_id == cohort_id).all()
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Username', 'Email', 'College', 'Department', 'Year', 'Assigned Date'])
        
        # Write user data
        for uc in user_cohorts:
            user = db.query(User).filter(User.id == uc.user_id).first()
            if user:
                writer.writerow([
                    user.username,
                    user.email,
                    user.college or '',
                    user.department or '',
                    user.year or '',
                    uc.assigned_at.strftime('%Y-%m-%d %H:%M:%S') if uc.assigned_at else ''
                ])
        
        csv_content = output.getvalue()
        output.close()
        
        from fastapi.responses import Response
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=cohort_{cohort_id}_users.csv"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export cohort users: {str(e)}")