# Integration code to add cohort endpoints to main.py
# This file contains the endpoints that need to be added to main.py

from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from database import get_db, Cohort, UserCohort, CohortCourse, User, Course, Admin, Enrollment
from auth import get_current_admin, require_role
from datetime import datetime
from typing import List, Optional
import csv
import io

# Import the cohort endpoint functions
from cohort_endpoints import (
    CohortCreate, CohortUpdate, CohortUserAdd, CohortCourseAssign,
    create_cohort, get_cohorts, get_cohort_details, update_cohort, delete_cohort,
    add_users_to_cohort, remove_user_from_cohort, assign_courses_to_cohort,
    remove_course_from_cohort, get_available_users, get_available_courses,
    export_cohort_users
)

# Add these endpoints to main.py:

# Cohort Management Endpoints
@app.post("/admin/cohorts")
async def create_cohort_endpoint(
    cohort_data: CohortCreate,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return await create_cohort(cohort_data, current_admin, db)

@app.get("/admin/cohorts")
async def get_cohorts_endpoint(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return await get_cohorts(page, limit, search, current_admin, db)

@app.get("/admin/cohorts/{cohort_id}")
async def get_cohort_details_endpoint(
    cohort_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return await get_cohort_details(cohort_id, current_admin, db)

@app.put("/admin/cohorts/{cohort_id}")
async def update_cohort_endpoint(
    cohort_id: int,
    cohort_data: CohortUpdate,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return await update_cohort(cohort_id, cohort_data, current_admin, db)

@app.delete("/admin/cohorts/{cohort_id}")
async def delete_cohort_endpoint(
    cohort_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return await delete_cohort(cohort_id, current_admin, db)

@app.post("/admin/cohorts/{cohort_id}/users")
async def add_users_to_cohort_endpoint(
    cohort_id: int,
    user_data: CohortUserAdd,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return await add_users_to_cohort(cohort_id, user_data, current_admin, db)

@app.delete("/admin/cohorts/{cohort_id}/users/{user_id}")
async def remove_user_from_cohort_endpoint(
    cohort_id: int,
    user_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return await remove_user_from_cohort(cohort_id, user_id, current_admin, db)

@app.post("/admin/cohorts/{cohort_id}/courses")
async def assign_courses_to_cohort_endpoint(
    cohort_id: int,
    course_data: CohortCourseAssign,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return await assign_courses_to_cohort(cohort_id, course_data, current_admin, db)

@app.delete("/admin/cohorts/{cohort_id}/courses/{course_id}")
async def remove_course_from_cohort_endpoint(
    cohort_id: int,
    course_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return await remove_course_from_cohort(cohort_id, course_id, current_admin, db)

@app.get("/admin/available-users")
async def get_available_users_endpoint(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return await get_available_users(current_admin, db)

@app.get("/admin/available-courses")
async def get_available_courses_endpoint(
    cohort_id: Optional[int] = None,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return await get_available_courses(cohort_id, current_admin, db)

@app.get("/admin/cohorts/{cohort_id}/export")
async def export_cohort_users_endpoint(
    cohort_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return await export_cohort_users(cohort_id, current_admin, db)

# Modified student courses endpoint with cohort-based access control
@app.get("/student/courses")
async def get_student_courses_with_cohort_access(
    current_user: User = Depends(require_role("Student")),
    db: Session = Depends(get_db)
):
    try:
        # Get all courses
        all_courses = db.query(Course).all()
        
        # Get enrolled courses
        enrolled_courses = db.query(Enrollment.course_id).filter(
            Enrollment.student_id == current_user.id
        ).all()
        enrolled_ids = [e[0] for e in enrolled_courses]
        
        # Get user's cohort information
        user_cohort = None
        cohort_course_ids = []
        
        if current_user.cohort_id:
            user_cohort = db.query(Cohort).filter(Cohort.id == current_user.cohort_id).first()
            # Get courses assigned to user's cohort
            cohort_courses = db.query(CohortCourse.course_id).filter(
                CohortCourse.cohort_id == current_user.cohort_id
            ).all()
            cohort_course_ids = [cc[0] for cc in cohort_courses]
        
        result = []
        for course in all_courses:
            # Get course statistics
            max_week = db.query(func.max(Module.week_number)).filter(Module.course_id == course.id).scalar()
            duration_weeks = max_week if max_week else 0
            
            total_modules = db.query(Module).filter(Module.course_id == course.id).count()
            total_sessions = db.query(SessionModel).join(Module).filter(Module.course_id == course.id).count()
            
            # Determine access level
            is_enrolled = course.id in enrolled_ids
            is_cohort_assigned = course.id in cohort_course_ids
            
            # Access logic:
            # 1. If user is in a cohort, they can only access cohort-assigned courses
            # 2. If user is not in a cohort, they can access all courses
            # 3. Enrolled courses are always accessible
            
            if current_user.cohort_id:
                # User is in a cohort
                if is_cohort_assigned or is_enrolled:
                    access_level = "accessible"
                else:
                    access_level = "locked"
            else:
                # User is not in a cohort - can access all courses
                access_level = "accessible"
            
            result.append({
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "duration_weeks": duration_weeks,
                "enrolled": is_enrolled,
                "total_modules": total_modules,
                "total_sessions": total_sessions,
                "access_level": access_level,
                "is_cohort_assigned": is_cohort_assigned,
                "cohort_restricted": current_user.cohort_id is not None and not is_cohort_assigned,
                "lock_reason": "This course is not assigned to your cohort" if current_user.cohort_id and not is_cohort_assigned and not is_enrolled else None
            })
        
        return {
            "courses": result,
            "user_cohort": {
                "id": user_cohort.id,
                "name": user_cohort.name,
                "instructor_name": user_cohort.instructor_name
            } if user_cohort else None
        }
    except Exception as e:
        logger.error(f"Get student courses error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch courses")

# Modified enrollment endpoint with cohort access control
@app.post("/student/courses/{course_id}/enroll")
async def enroll_with_cohort_check(
    course_id: int,
    current_user: User = Depends(require_role("Student")),
    db: Session = Depends(get_db)
):
    try:
        # Check if course exists
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Check if already enrolled
        existing = db.query(Enrollment).filter(
            Enrollment.student_id == current_user.id,
            Enrollment.course_id == course_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Already enrolled in this course")
        
        # Cohort access check
        if current_user.cohort_id:
            # User is in a cohort - check if course is assigned to their cohort
            cohort_course = db.query(CohortCourse).filter(
                CohortCourse.cohort_id == current_user.cohort_id,
                CohortCourse.course_id == course_id
            ).first()
            
            if not cohort_course:
                raise HTTPException(
                    status_code=403, 
                    detail="This course is not assigned to your cohort. Please contact your administrator."
                )
        
        # Create enrollment
        enrollment = Enrollment(
            student_id=current_user.id, 
            course_id=course_id,
            cohort_id=current_user.cohort_id  # Track cohort in enrollment
        )
        db.add(enrollment)
        db.commit()
        
        return {
            "message": "Successfully enrolled in course",
            "course_title": course.title,
            "cohort_enrollment": current_user.cohort_id is not None
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Course enrollment error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to enroll in course")

# Bulk upload users to cohort endpoint
@app.post("/admin/cohorts/{cohort_id}/bulk-upload")
async def bulk_upload_users_to_cohort(
    cohort_id: int,
    file: UploadFile = File(...),
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    try:
        # Check if cohort exists
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in ['.csv', '.xlsx', '.xls']:
            raise HTTPException(status_code=400, detail="Only CSV and Excel files are allowed")
        
        content = await file.read()
        records = []
        
        if file_ext == '.csv':
            try:
                csv_content = content.decode('utf-8')
                csv_reader = csv.DictReader(io.StringIO(csv_content))
                records = list(csv_reader)
            except UnicodeDecodeError:
                csv_content = content.decode('utf-8-sig')
                csv_reader = csv.DictReader(io.StringIO(csv_content))
                records = list(csv_reader)
        else:
            try:
                import pandas as pd
                df = pd.read_excel(io.BytesIO(content))
                records = df.to_dict('records')
            except ImportError:
                raise HTTPException(status_code=500, detail="Excel processing not available")
        
        if not records:
            raise HTTPException(status_code=400, detail="No data found in file")
        
        created_users = []
        errors = []
        
        for row_num, row in enumerate(records, 1):
            try:
                username = str(row.get('Username') or row.get('username') or '').strip()
                email = str(row.get('Email') or row.get('email') or '').strip()
                password = str(row.get('Password') or row.get('password') or '').strip()
                user_type = str(row.get('Type') or row.get('type') or 'Student').strip()
                college = str(row.get('College') or row.get('college') or '').strip()
                department = str(row.get('Department') or row.get('department') or '').strip()
                year = str(row.get('Year') or row.get('year') or '').strip()
                
                if not all([username, email, password]):
                    errors.append(f"Row {row_num}: Missing required fields")
                    continue
                
                # Check for duplicates
                if db.query(User).filter(User.username == username).first():
                    errors.append(f"Row {row_num}: Username '{username}' already exists")
                    continue
                
                if db.query(User).filter(User.email == email).first():
                    errors.append(f"Row {row_num}: Email '{email}' already exists")
                    continue
                
                # Create user
                from auth import get_password_hash
                user = User(
                    username=username,
                    email=email,
                    password_hash=get_password_hash(password),
                    role=user_type if user_type in ['Student', 'Faculty'] else 'Student',
                    user_type=user_type if user_type in ['Student', 'Faculty'] else 'Student',
                    college=college,
                    department=department,
                    year=year,
                    cohort_id=cohort_id
                )
                
                db.add(user)
                db.flush()  # Get user ID
                
                # Add to cohort
                user_cohort = UserCohort(
                    user_id=user.id,
                    cohort_id=cohort_id,
                    assigned_by=current_admin.id
                )
                db.add(user_cohort)
                
                created_users.append({
                    'username': username,
                    'email': email,
                    'type': user_type
                })
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        if created_users:
            db.commit()
        else:
            db.rollback()
        
        return {
            "message": f"Successfully created {len(created_users)} users and added to cohort",
            "created_users": [u['username'] for u in created_users],
            "errors": errors[:10],  # Limit errors shown
            "total_processed": len(records),
            "success_count": len(created_users),
            "error_count": len(errors)
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Bulk upload to cohort error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bulk upload failed: {str(e)}")