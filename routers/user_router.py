from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from database import get_db, User, Admin, Presenter, Manager, Mentor
from auth import get_current_admin_or_presenter, get_password_hash
from schemas import UserCreate, UserUpdate
import logging
import csv
import io
import os
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["user_management"])

# Import logging functions
from main import log_admin_action

@router.get("/users/bulk-upload-template")
async def download_bulk_upload_template():
    """Download CSV template for bulk user upload"""
    template_path = "uploads/user_bulk_upload_template.csv"
    if os.path.exists(template_path):
        return FileResponse(
            path=template_path,
            filename="user_bulk_upload_template.csv",
            media_type="text/csv"
        )
    else:
        raise HTTPException(status_code=404, detail="Template file not found")

@router.post("/users/bulk-upload")
async def bulk_upload_users(
    file: UploadFile = File(...),
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Bulk upload users from Excel/CSV file"""
    try:
        logger.info(f"Bulk upload started - File: {file.filename}, Content-Type: {file.content_type}")
        
        # Check file extension
        if not file.filename or not file.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
            raise HTTPException(
                status_code=400, 
                detail="Only Excel (.xlsx, .xls) and CSV files are supported. Please check your file extension."
            )
        
        # Read file content
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="File is empty or could not be read")
        
        logger.info(f"File content size: {len(content)} bytes")
        
        # Parse file based on extension
        try:
            if file.filename.lower().endswith('.csv'):
                # Try different encodings for CSV
                try:
                    df = pd.read_csv(io.BytesIO(content), encoding='utf-8')
                except UnicodeDecodeError:
                    try:
                        df = pd.read_csv(io.BytesIO(content), encoding='latin-1')
                    except UnicodeDecodeError:
                        df = pd.read_csv(io.BytesIO(content), encoding='cp1252')
            else:
                df = pd.read_excel(io.BytesIO(content))
        except Exception as e:
            logger.error(f"File parsing error: {str(e)}")
            raise HTTPException(
                status_code=400, 
                detail=f"Could not parse file. Please ensure it's a valid Excel or CSV file. Error: {str(e)}"
            )
        
        # Check if dataframe is empty
        if df.empty:
            raise HTTPException(status_code=400, detail="File contains no data rows")
        
        logger.info(f"Parsed {len(df)} rows with columns: {list(df.columns)}")
        
        # Validate required columns (case-insensitive)
        df.columns = df.columns.str.lower().str.strip()
        required_columns = ['username', 'email', 'password']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            available_columns = list(df.columns)
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required columns: {', '.join(missing_columns)}. Available columns: {', '.join(available_columns)}"
            )
        
        success_count = 0
        error_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Skip empty rows
                if pd.isna(row['username']) or pd.isna(row['email']) or pd.isna(row['password']):
                    errors.append(f"Row {index + 2}: Missing required data (username, email, or password)")
                    error_count += 1
                    continue
                
                username = str(row['username']).strip()
                email = str(row['email']).strip()
                password = str(row['password']).strip()
                
                # Basic validation
                if not username or not email or not password:
                    errors.append(f"Row {index + 2}: Empty username, email, or password")
                    error_count += 1
                    continue
                
                # Check if email already exists (allow duplicate usernames)
                if db.query(User).filter(User.email == email).first():
                    errors.append(f"Row {index + 2}: Email '{email}' already exists")
                    error_count += 1
                    continue
                
                # Create user
                hashed_password = get_password_hash(password)
                
                user = User(
                    username=username,
                    email=email,
                    password_hash=hashed_password,
                    role=str(row.get('role', 'Student')) if pd.notna(row.get('role')) else 'Student',
                    college=str(row.get('college', '')) if pd.notna(row.get('college')) else None,
                    department=str(row.get('department', '')) if pd.notna(row.get('department')) else None,
                    year=str(row.get('year', '')) if pd.notna(row.get('year')) else None,
                    user_type=str(row.get('user_type', 'Student')) if pd.notna(row.get('user_type')) else 'Student',
                    github_link=str(row.get('github_link', '')) if pd.notna(row.get('github_link')) else None
                )
                
                db.add(user)
                db.flush()  # Get the user ID
                
                # Send welcome email using template
                try:
                    from notification_service import NotificationService
                    from database import EmailTemplate
                    
                    service = NotificationService(db)
                    
                    # Get the User Registration Welcome Email template
                    template = db.query(EmailTemplate).filter(
                        EmailTemplate.name == "User Registration Welcome Email"
                    ).first()
                    
                    if template and template.is_active:
                        # Format template with user data
                        template_context = {
                            "username": user.username,
                            "email": user.email,
                            "password": password,
                            "college": user.college or "Not specified",
                            "department": user.department or "Not specified",
                            "year": user.year or "Not specified"
                        }
                        
                        formatted_subject = template.subject.format(**template_context)
                        # Convert newlines to HTML breaks for proper email formatting
                        formatted_body = template.body.format(**template_context).replace('\n', '<br>')
                        
                        service.send_email_notification(
                            user_id=user.id,
                            email=user.email,
                            subject=formatted_subject,
                            body=formatted_body
                        )
                    
                except Exception as e:
                    logger.warning(f"Failed to send welcome email to {user.email}: {str(e)}")
                
                success_count += 1
                
            except Exception as e:
                logger.error(f"Error processing row {index + 2}: {str(e)}")
                errors.append(f"Row {index + 2}: {str(e)}")
                error_count += 1
                continue
        
        if success_count > 0:
            db.commit()
            logger.info(f"Bulk upload completed: {success_count} success, {error_count} errors")
        else:
            db.rollback()
            logger.warning("No users were created due to errors")
        
        return {
            "message": f"Bulk upload completed. {success_count} users created successfully, {error_count} errors.",
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors[:20]  # Return first 20 errors
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Bulk upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process bulk upload: {str(e)}")

@router.post("/users")
async def create_user(user_data: UserCreate, current_admin = Depends(get_current_admin_or_presenter), db: Session = Depends(get_db)):
    try:
        # Allow duplicate usernames; enforce unique email only
        if db.query(User).filter(User.email == user_data.email).first():
            raise HTTPException(status_code=400, detail="Email already exists")
        
        hashed_password = get_password_hash(user_data.password)
        
        joining_date = None
        if user_data.joining_date:
            try:
                from datetime import datetime
                joining_date = datetime.fromisoformat(user_data.joining_date)
            except:
                pass
        
        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed_password,
            role=user_data.user_type or "Student",
            college=user_data.college,
            department=user_data.department,
            year=user_data.year,
            user_type=user_data.user_type or "Student",
            experience=user_data.experience,
            designation=user_data.designation,
            specialization=user_data.specialization,
            employment_type=user_data.employment_type,
            joining_date=joining_date,
            github_link=user_data.github_link
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Send welcome email using template
        try:
            from notification_service import NotificationService
            from database import EmailTemplate
            
            service = NotificationService(db)
            
            # Get the User Registration Welcome Email template
            template = db.query(EmailTemplate).filter(
                EmailTemplate.name == "User Registration Welcome Email"
            ).first()
            
            if template and template.is_active:
                # Format template with user data
                template_context = {
                    "username": user.username,
                    "email": user.email,
                    "password": user_data.password,
                    "college": user.college or "Not specified",
                    "department": user.department or "Not specified",
                    "year": user.year or "Not specified"
                }
                
                formatted_subject = template.subject.format(**template_context)
                # Convert newlines to HTML breaks for proper email formatting
                formatted_body = template.body.format(**template_context).replace('\n', '<br>')
                
                email_log = service.send_email_notification(
                    user_id=user.id,
                    email=user.email,
                    subject=formatted_subject,
                    body=formatted_body
                )
                
                if email_log.status == "sent":
                    logger.info(f"Registration welcome email sent successfully to {user.email}")
                
        except Exception as e:
            logger.warning(f"Failed to send welcome email to {user.email}: {str(e)}")
        
        if hasattr(current_admin, 'username') and db.query(Admin).filter(Admin.id == current_admin.id).first():
            log_admin_action(
                admin_id=current_admin.id,
                admin_username=current_admin.username,
                action_type="CREATE",
                resource_type="USER",
                resource_id=user.id,
                details=f"Created user: {user.username} ({user.email})"
            )
        
        return {"message": "User created successfully", "user_id": user.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create user error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")

@router.get("/users")
async def get_all_users(
    page: int = 1, 
    limit: int = 10000, 
    search: Optional[str] = None,
    role: Optional[str] = None,
    college: Optional[str] = None,
    current_user = Depends(get_current_admin_or_presenter), 
    db: Session = Depends(get_db)
):
    try:
        query = db.query(User).filter(User.user_type.in_(['Student', 'Faculty']))
        
        if search:
            query = query.filter(
                or_(
                    User.username.contains(search),
                    User.email.contains(search),
                    User.college.contains(search)
                )
            )
        
        if role:
            query = query.filter(User.user_type == role)
        
        if college:
            query = query.filter(User.college == college)
        
        total = query.count()
        users = query.offset((page - 1) * limit).limit(limit).all()
        
        return {
            "users": [{
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role,
                "college": u.college,
                "department": u.department,
                "year": u.year,
                "user_type": u.user_type,
                "experience": u.experience,
                "designation": u.designation,
                "specialization": u.specialization,
                "employment_type": u.employment_type,
                "joining_date": u.joining_date,
                "github_link": u.github_link,
                "active": True,
                "created_at": u.created_at
            } for u in users],
            "total": total,
            "page": page,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Get users error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")

@router.put("/users/{user_id}")
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
        
        # Allow duplicate usernames; enforce unique email only
        if user_data.email and db.query(User).filter(User.email == user_data.email, User.id != user_id).first():
            raise HTTPException(status_code=400, detail="Email already exists")
        
        update_data = user_data.dict(exclude_unset=True)
        if 'password' in update_data:
            update_data['password_hash'] = get_password_hash(update_data.pop('password'))
        
        if 'joining_date' in update_data and update_data['joining_date']:
            try:
                from datetime import datetime
                update_data['joining_date'] = datetime.fromisoformat(update_data['joining_date'])
            except:
                update_data.pop('joining_date', None)
        
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

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    try:
        # Find the user first
        user = db.query(User).filter(User.id == user_id).first()
        admin_user = db.query(Admin).filter(Admin.id == user_id).first()
        presenter_user = db.query(Presenter).filter(Presenter.id == user_id).first()
        mentor_user = db.query(Mentor).filter(Mentor.id == user_id).first()
        manager_user = db.query(Manager).filter(Manager.id == user_id).first()
        
        if user:
            username = user.username
            user_type = user.user_type
            
            # Delete related records safely
            try:
                # Delete resource views first (no foreign key constraint)
                from resource_analytics_models import ResourceView
                db.query(ResourceView).filter(ResourceView.student_id == user_id).delete(synchronize_session=False)
                
                # Delete other related records if tables exist
                try:
                    from database import UserCohort, Enrollment
                    db.query(UserCohort).filter(UserCohort.user_id == user_id).delete(synchronize_session=False)
                    db.query(Enrollment).filter(Enrollment.student_id == user_id).delete(synchronize_session=False)
                except Exception:
                    pass  # Tables might not exist
                    
            except Exception as e:
                logger.warning(f"Could not delete some related records: {str(e)}")
            
            # Delete the user
            db.delete(user)
            
        elif admin_user:
            if admin_user.id == current_admin.id:
                raise HTTPException(status_code=400, detail="Cannot delete your own account")
            
            username = admin_user.username
            user_type = "Admin"
            db.delete(admin_user)
            
        elif presenter_user:
            username = presenter_user.username
            user_type = "Presenter"
            db.delete(presenter_user)
            
        elif mentor_user:
            username = mentor_user.username
            user_type = "Mentor"
            db.delete(mentor_user)
            
        elif manager_user:
            username = manager_user.username
            user_type = "Manager"
            db.delete(manager_user)
            
        else:
            raise HTTPException(status_code=404, detail="User not found")
        
        db.commit()
        
        # Log the deletion
        try:
            if hasattr(current_admin, 'username'):
                log_admin_action(
                    admin_id=current_admin.id,
                    admin_username=current_admin.username,
                    action_type="DELETE",
                    resource_type="USER",
                    resource_id=user_id,
                    details=f"Deleted {user_type}: {username}"
                )
        except Exception as e:
            logger.warning(f"Could not log deletion: {str(e)}")
        
        return {"message": f"{user_type} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete user error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")