from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from database import get_db, User, Admin, Presenter, Manager, Mentor, Course, Module, Session as SessionModel, Enrollment, Cohort, UserCohort, CohortCourse, PresenterCohort, Resource, Attendance, Certificate, Forum, ForumPost, SessionContent, Event, SystemSettings, AdminLog, PresenterLog, MentorLog, StudentLog, Notification, EmailLog, EmailRecipient, NotificationPreference
from auth import get_current_admin_or_presenter, get_password_hash
from schemas import CourseCreate, CourseUpdate, AdminCreate, PresenterCreate, ChangePasswordRequest, UserCreate, UserUpdate, ModuleCreate, ModuleUpdate, SessionCreate, SessionUpdate, ResourceCreate, AttendanceCreate, AttendanceBulkCreate, ForumCreate, ForumPostCreate, SessionContentCreate, CertificateGenerate, ProgressUpdate, NotificationCreate
from datetime import datetime, timedelta
from typing import Optional, List
import logging
import csv
import io
import os

router = APIRouter()
logger = logging.getLogger(__name__)

# Admin Management Endpoints
@router.post("/admin/create-admin")
async def create_admin(
    admin_data: AdminCreate,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        if db.query(Admin).filter(Admin.username == admin_data.username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        if db.query(Admin).filter(Admin.email == admin_data.email).first():
            raise HTTPException(status_code=400, detail="Email already exists")
        
        hashed_password = get_password_hash(admin_data.password)
        admin = Admin(
            username=admin_data.username,
            email=admin_data.email,
            password_hash=hashed_password
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        return {"message": "Admin created successfully", "admin_id": admin.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create admin error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create admin")

@router.post("/admin/create-presenter")
async def create_presenter(
    presenter_data: PresenterCreate,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        if db.query(Presenter).filter(Presenter.username == presenter_data.username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        if db.query(Presenter).filter(Presenter.email == presenter_data.email).first():
            raise HTTPException(status_code=400, detail="Email already exists")
        
        hashed_password = get_password_hash(presenter_data.password)
        presenter = Presenter(
            username=presenter_data.username,
            email=presenter_data.email,
            password_hash=hashed_password
        )
        db.add(presenter)
        db.commit()
        db.refresh(presenter)
        
        return {"message": "Presenter created successfully", "presenter_id": presenter.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create presenter error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create presenter")

@router.post("/admin/create-manager")
async def create_manager(
    manager_data: AdminCreate,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        if db.query(Manager).filter(Manager.username == manager_data.username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        if db.query(Manager).filter(Manager.email == manager_data.email).first():
            raise HTTPException(status_code=400, detail="Email already exists")
        
        hashed_password = get_password_hash(manager_data.password)
        manager = Manager(
            username=manager_data.username,
            email=manager_data.email,
            password_hash=hashed_password
        )
        db.add(manager)
        db.commit()
        db.refresh(manager)
        
        return {"message": "Manager created successfully", "manager_id": manager.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create manager error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create manager")

@router.get("/admin/presenters")
async def get_all_presenters(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        presenters = db.query(Presenter).all()
        
        return {
            "presenters": [{
                "id": p.id,
                "username": p.username,
                "email": p.email,
                "is_active": getattr(p, 'is_active', True),
                "created_at": p.created_at
            } for p in presenters]
        }
    except Exception as e:
        logger.error(f"Get presenters error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch presenters")

@router.post("/admin/change-password")
async def change_admin_password(
    password_data: ChangePasswordRequest,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        from auth import verify_password
        if not verify_password(password_data.current_password, current_admin.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        
        current_admin.password_hash = get_password_hash(password_data.new_password)
        db.commit()
        
        return {"message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Change password error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to change password")

# User Management
@router.post("/admin/users")
async def create_user(
    user_data: UserCreate, 
    current_admin = Depends(get_current_admin_or_presenter), 
    db: Session = Depends(get_db)
):
    try:
        if db.query(User).filter(User.username == user_data.username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        if db.query(User).filter(User.email == user_data.email).first():
            raise HTTPException(status_code=400, detail="Email already exists")
        
        hashed_password = get_password_hash(user_data.password)
        
        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed_password,
            role=user_data.user_type or "Student",
            college=user_data.college,
            department=user_data.department,
            year=user_data.year,
            user_type=user_data.user_type or "Student",
            github_link=user_data.github_link
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return {"message": "User created successfully", "user_id": user.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create user error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create user")

@router.get("/admin/users")
async def get_all_users(
    page: int = 1, 
    limit: int = 1000,  # Increased limit to get all users for chat
    search: Optional[str] = None,
    role: Optional[str] = None,
    college: Optional[str] = None,
    current_user = Depends(get_current_admin_or_presenter), 
    db: Session = Depends(get_db)
):
    try:
        all_users = []
        
        # Fetch from User table (Students and Faculty)
        users = db.query(User).filter(User.user_type.in_(['Student', 'Faculty'])).all()
        for u in users:
            all_users.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.user_type,
                "college": u.college,
                "department": u.department,
                "year": u.year,
                "user_type": u.user_type,
                "github_link": u.github_link,
                "active": True,
                "created_at": u.created_at
            })
        
        # Fetch from Admin table
        admins = db.query(Admin).all()
        for a in admins:
            all_users.append({
                "id": a.id,
                "username": a.username,
                "email": a.email,
                "role": "Admin",
                "college": None,
                "department": None,
                "year": None,
                "user_type": "Admin",
                "github_link": None,
                "active": getattr(a, 'is_active', True),
                "created_at": a.created_at
            })
        
        # Fetch from Manager table
        managers = db.query(Manager).all()
        for m in managers:
            all_users.append({
                "id": m.id,
                "username": m.username,
                "email": m.email,
                "role": "Manager",
                "college": None,
                "department": None,
                "year": None,
                "user_type": "Manager",
                "github_link": None,
                "active": getattr(m, 'is_active', True),
                "created_at": m.created_at
            })
        
        # Fetch from Presenter table
        presenters = db.query(Presenter).all()
        for p in presenters:
            all_users.append({
                "id": p.id,
                "username": p.username,
                "email": p.email,
                "role": "Presenter",
                "college": None,
                "department": None,
                "year": None,
                "user_type": "Presenter",
                "github_link": None,
                "active": getattr(p, 'is_active', True),
                "created_at": p.created_at
            })
        
        # Fetch from Mentor table
        mentors = db.query(Mentor).all()
        for m in mentors:
            all_users.append({
                "id": m.id,
                "username": m.username,
                "email": m.email,
                "role": "Mentor",
                "college": None,
                "department": None,
                "year": None,
                "user_type": "Mentor",
                "github_link": None,
                "active": getattr(m, 'is_active', True),
                "created_at": m.created_at
            })
        
        # Apply search filter if provided
        if search:
            all_users = [u for u in all_users if 
                search.lower() in u['username'].lower() or 
                search.lower() in u['email'].lower() or
                (u['college'] and search.lower() in u['college'].lower())]
        
        # Apply role filter if provided
        if role:
            all_users = [u for u in all_users if u['user_type'] == role]
        
        # Apply college filter if provided
        if college:
            all_users = [u for u in all_users if u['college'] and college.lower() in u['college'].lower()]
        
        total = len(all_users)
        
        # Apply pagination
        start = (page - 1) * limit
        end = start + limit
        paginated_users = all_users[start:end]
        
        return {
            "users": paginated_users,
            "total": total,
            "page": page,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Get users error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")

@router.put("/admin/users/{user_id}")
async def update_user(
    user_id: int, 
    user_data: UserUpdate, 
    current_admin = Depends(get_current_admin_or_presenter), 
    db: Session = Depends(get_db)
):
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user_data.username and db.query(User).filter(User.username == user_data.username, User.id != user_id).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        if user_data.email and db.query(User).filter(User.email == user_data.email, User.id != user_id).first():
            raise HTTPException(status_code=400, detail="Email already exists")
        
        update_data = user_data.dict(exclude_unset=True)
        if 'password' in update_data:
            update_data['password_hash'] = get_password_hash(update_data.pop('password'))
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        db.commit()
        return {"message": "User updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update user error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update user")

@router.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        db.delete(user)
        db.commit()
        
        return {"message": "User deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete user error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete user")

# Course Management
@router.post("/admin/courses")
async def create_course(
    course_data: CourseCreate, 
    current_user = Depends(get_current_admin_or_presenter), 
    db: Session = Depends(get_db)
):
    try:
        course = Course(
            title=course_data.title,
            description=course_data.description,
            duration_weeks=course_data.duration_weeks,
            sessions_per_week=course_data.sessions_per_week,
            is_active=course_data.is_active
        )
        db.add(course)
        db.commit()
        db.refresh(course)
        
        return {"message": "Course created successfully", "course_id": course.id}
    except Exception as e:
        db.rollback()
        logger.error(f"Create course error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create course")

@router.put("/admin/courses/{course_id}")
async def update_course(
    course_id: int,
    course_data: CourseUpdate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        update_data = course_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(course, field, value)
        
        db.commit()
        return {"message": "Course updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update course error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update course")

@router.delete("/admin/courses/{course_id}")
async def delete_course(
    course_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        db.delete(course)
        db.commit()
        
        return {"message": "Course deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete course error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete course")

# Module Management
@router.post("/admin/modules")
async def create_module(
    module_data: ModuleCreate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        course = db.query(Course).filter(Course.id == module_data.course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        module = Module(**module_data.dict())
        db.add(module)
        db.commit()
        db.refresh(module)
        
        return {"message": "Module created successfully", "module_id": module.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create module error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create module")

@router.get("/admin/module/{module_id}")
async def get_module(
    module_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        module = db.query(Module).filter(Module.id == module_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        
        return {
            "id": module.id,
            "course_id": module.course_id,
            "week_number": module.week_number,
            "title": module.title,
            "description": module.description,
            "start_date": module.start_date,
            "end_date": module.end_date,
            "created_at": module.created_at
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get module error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch module")

@router.put("/admin/modules/{module_id}")
async def update_module(
    module_id: int,
    module_data: ModuleUpdate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        module = db.query(Module).filter(Module.id == module_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        
        update_data = module_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(module, field, value)
        
        db.commit()
        return {"message": "Module updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update module error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update module")

@router.delete("/admin/modules/{module_id}")
async def delete_module(
    module_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        module = db.query(Module).filter(Module.id == module_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        
        db.delete(module)
        db.commit()
        
        return {"message": "Module deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete module error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete module")

# Session Management
@router.post("/admin/sessions")
async def create_session(
    session_data: SessionCreate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        module = db.query(Module).filter(Module.id == session_data.module_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        
        scheduled_datetime = None
        if session_data.scheduled_date and session_data.scheduled_time:
            try:
                date_str = f"{session_data.scheduled_date} {session_data.scheduled_time}"
                scheduled_datetime = datetime.strptime(date_str, '%d-%m-%Y %H:%M')
            except ValueError:
                pass
        
        session = SessionModel(
            module_id=session_data.module_id,
            session_number=session_data.session_number,
            title=session_data.title,
            description=session_data.description,
            scheduled_time=scheduled_datetime,
            duration_minutes=session_data.duration_minutes,
            zoom_link=getattr(session_data, 'meeting_link', None)
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return {"message": "Session created successfully", "session_id": session.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create session error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create session")

@router.put("/admin/sessions/{session_id}")
async def update_session(
    session_id: int,
    session_data: SessionUpdate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        update_data = session_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(session, field, value)
        
        db.commit()
        return {"message": "Session updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update session error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update session")

@router.delete("/admin/sessions/{session_id}")
async def delete_session(
    session_id: int,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        db.delete(session)
        db.commit()
        
        return {"message": "Session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete session error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete session")

# Bulk Upload Templates
@router.get("/admin/download-student-template")
async def download_student_template(
    current_user = Depends(get_current_admin_or_presenter)
):
    try:
        csv_content = "Username,Email,Password,College,Department,Year,Github_Link\n"
        csv_content += "john_doe,john@example.com,password123,MIT University,Computer Science,2024,https://github.com/johndoe\n"
        csv_content += "jane_smith,jane@example.com,password456,Stanford University,Engineering,2023,https://github.com/janesmith\n"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "inline; filename=student_template.csv"}
        )
    except Exception as e:
        logger.error(f"Download student template error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate student template")

@router.get("/admin/download-faculty-template")
async def download_faculty_template(
    current_user = Depends(get_current_admin_or_presenter)
):
    try:
        csv_content = "Username,Email,Password,College,Department,Experience,Designation,Specialization,Employment_Type,Joining_Date,Github_Link\n"
        csv_content += "dr_sarah_jones,sarah@university.edu,faculty123,MIT University,Computer Science,10,Associate Professor,Machine Learning Data Science,Full-time,2020-01-15,https://github.com/drjones\n"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "inline; filename=faculty_template.csv"}
        )
    except Exception as e:
        logger.error(f"Download faculty template error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate faculty template")

@router.post("/admin/users/bulk-upload")
async def bulk_upload_users(
    file: UploadFile = File(...),
    user_type_filter: str = Form("Student"),
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in ['.csv', '.xlsx', '.xls']:
            raise HTTPException(status_code=400, detail="Only CSV and Excel files are allowed")
        
        if user_type_filter not in ['Student', 'Faculty']:
            raise HTTPException(status_code=400, detail="Invalid user type filter")
        
        content = await file.read()
        records = []
        
        if file_ext == '.csv':
            csv_content = content.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            records = list(csv_reader)
        
        created_users = []
        errors = []
        
        for row_num, row in enumerate(records, 1):
            try:
                username = str(row.get('Username') or '').strip()
                email = str(row.get('Email') or '').strip()
                password = str(row.get('Password') or '').strip()
                college = str(row.get('College') or '').strip()
                department = str(row.get('Department') or '').strip()
                year = str(row.get('Year') or '').strip()
                
                if not all([username, email, password]):
                    errors.append(f"Row {row_num}: Missing required fields")
                    continue
                
                if db.query(User).filter(User.username == username).first():
                    errors.append(f"Row {row_num}: Username '{username}' already exists")
                    continue
                
                if db.query(User).filter(User.email == email).first():
                    errors.append(f"Row {row_num}: Email '{email}' already exists")
                    continue
                
                user = User(
                    username=username,
                    email=email,
                    password_hash=get_password_hash(password),
                    role=user_type_filter,
                    user_type=user_type_filter,
                    college=college,
                    department=department,
                    year=year or "2024",
                    github_link=str(row.get('Github_Link') or row.get('github_link') or '').strip() if (row.get('Github_Link') or row.get('github_link')) else None
                )
                
                db.add(user)
                created_users.append({'username': username, 'email': email})
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        if created_users:
            db.commit()
        else:
            db.rollback()
        
        return {
            "message": f"Successfully created {len(created_users)} {user_type_filter.lower()}s",
            "created_users": [u['username'] for u in created_users],
            "errors": errors[:10],
            "success_count": len(created_users),
            "error_count": len(errors)
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Bulk upload users error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")