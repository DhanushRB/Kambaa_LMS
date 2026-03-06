from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from typing import List, Optional
from datetime import datetime, timedelta
import io
import pandas as pd
from database import get_db, User, Cohort, Enrollment, Attendance, Session as SessionModel, Module, Course
from assignment_quiz_models import Assignment, AssignmentSubmission, AssignmentGrade, Quiz, QuizAttempt, QuizResult
from auth import get_current_user_any_role
import logging

router = APIRouter(tags=["user_reports"])
logger = logging.getLogger(__name__)

@router.get("/users")
async def get_report_users(
    page: int = 1,
    limit: int = 50,
    search: Optional[str] = None,
    role: Optional[str] = None,
    cohort_id: Optional[int] = None,
    has_github: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_any_role)
):
    try:
        query = db.query(User)
        
        if search:
            search_filter = or_(
                User.username.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
            query = query.filter(search_filter)
            
        if role:
            query = query.filter(User.role == role)
            
        if cohort_id:
            query = query.filter(User.cohort_id == cohort_id)
            
        if has_github == 'true':
            query = query.filter(User.github_link.isnot(None), User.github_link != '')
        elif has_github == 'false':
            query = query.filter(or_(User.github_link.is_(None), User.github_link == ''))

        total = query.count()
        users = query.offset((page - 1) * limit).limit(limit).all()
        
        user_list = []
        for user in users:
            cohort_name = db.query(Cohort.name).filter(Cohort.id == user.cohort_id).scalar()
            user_list.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "college": user.college,
                "cohort_name": cohort_name
            })
            
        return {
            "total": total,
            "page": page,
            "total_pages": (total + limit - 1) // limit,
            "users": user_list
        }
    except Exception as e:
        logger.error(f"Error fetching report users: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")

@router.get("/consolidated")
async def get_consolidated_stats(
    page: int = 1,
    limit: int = 50,
    search: Optional[str] = None,
    role: Optional[str] = None,
    cohort_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    try:
        # Reusing user search logic
        query = db.query(User)
        if search:
            query = query.filter(or_(User.username.ilike(f"%{search}%"), User.email.ilike(f"%{search}%")))
        if role:
            query = query.filter(User.role == role)
        if cohort_id:
            query = query.filter(User.cohort_id == cohort_id)

        total = query.count()
        users = query.offset((page - 1) * limit).limit(limit).all()
        
        results = []
        for user in users:
            # Attendance stats
            attendance_records = db.query(Attendance).filter(Attendance.student_id == user.id).all()
            total_attendance = len(attendance_records)
            attended_count = sum(1 for a in attendance_records if a.attended)
            attendance_rate = (attended_count / total_attendance * 100) if total_attendance > 0 else 0
            
            # Assignment stats
            assignment_grades = db.query(AssignmentGrade).filter(AssignmentGrade.student_id == user.id).all()
            avg_assignment = sum(g.percentage for g in assignment_grades) / len(assignment_grades) if assignment_grades else 0
            
            # Quiz stats
            quiz_results = db.query(QuizResult).filter(QuizResult.student_id == user.id).all()
            avg_quiz = sum(r.percentage for r in quiz_results) / len(quiz_results) if quiz_results else 0
            
            cohort_name = db.query(Cohort.name).filter(Cohort.id == user.cohort_id).scalar()
            
            results.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "cohort_name": cohort_name,
                "activities_count": db.query(AdminLog).filter(AdminLog.admin_username == user.username).count(), # Conceptual
                "assignments_submitted": len(assignment_grades),
                "assignments_avg": round(avg_assignment, 2),
                "quizzes_attempted": len(quiz_results),
                "quizzes_avg": round(avg_quiz, 2),
                "attendance_rate": round(attendance_rate, 2)
            })
            
        return {
            "total": total,
            "page": page,
            "total_pages": (total + limit - 1) // limit,
            "users": results
        }
    except Exception as e:
        logger.error(f"Error fetching consolidated stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch stats")

@router.get("/{user_id}/summary")
async def get_user_summary(user_id: int, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user: raise HTTPException(status_code=404, detail="User not found")
        
        # Enrollment count
        enrollments_count = db.query(Enrollment).filter(Enrollment.student_id == user_id).count()
        
        # Assignment stats
        assignment_grades = db.query(AssignmentGrade).filter(AssignmentGrade.student_id == user_id).all()
        avg_assignment = sum(g.percentage for g in assignment_grades) / len(assignment_grades) if assignment_grades else 0
        
        # Attendance stats
        attendance_records = db.query(Attendance).filter(Attendance.student_id == user_id).all()
        total_attendance = len(attendance_records)
        attended_count = sum(1 for a in attendance_records if a.attended)
        attendance_rate = (attended_count / total_attendance * 100) if total_attendance > 0 else 0
        
        return {
            "stats": {
                "total_activities": 0, # Placeholder or implement via logs
                "enrollments_count": enrollments_count,
                "assignments": {"average_score": round(avg_assignment, 2)},
                "attendance": {"attendance_rate": round(attendance_rate, 2)}
            }
        }
    except Exception as e:
        logger.error(f"Error fetching user summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch summary")

@router.get("/{user_id}/activities")
async def get_user_activities(user_id: int, page: int = 1, limit: int = 50, db: Session = Depends(get_db)):
    # Placeholder for user activities tracking
    return {"activities": [], "total": 0}

@router.get("/{user_id}/enrollments")
async def get_user_enrollments(user_id: int, db: Session = Depends(get_db)):
    try:
        enrollments = db.query(Enrollment).filter(Enrollment.student_id == user_id).all()
        results = []
        for e in enrollments:
            course = db.query(Course).filter(Course.id == e.course_id).first()
            results.append({
                "id": e.id,
                "course_title": course.title if course else "Unknown Course",
                "enrolled_at": e.enrolled_at,
                "progress": e.progress,
                "status": e.payment_status
            })
        return {"enrollments": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/assignments")
async def get_user_assignments(user_id: int, db: Session = Depends(get_db)):
    try:
        grades = db.query(AssignmentGrade).filter(AssignmentGrade.student_id == user_id).all()
        results = []
        for g in grades:
            assignment = db.query(Assignment).filter(Assignment.id == g.assignment_id).first()
            results.append({
                "title": assignment.title if assignment else "Unknown Assignment",
                "marks_obtained": g.marks_obtained,
                "total_marks": g.total_marks,
                "percentage": g.percentage,
                "graded_at": g.graded_at
            })
        return {"assignments": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/quizzes")
async def get_user_quizzes(user_id: int, db: Session = Depends(get_db)):
    try:
        results = db.query(QuizResult).filter(QuizResult.student_id == user_id).all()
        output = []
        for r in results:
            quiz = db.query(Quiz).filter(Quiz.id == r.quiz_id).first()
            output.append({
                "title": quiz.title if quiz else "Unknown Quiz",
                "marks_obtained": r.marks_obtained,
                "total_marks": r.total_marks,
                "percentage": r.percentage,
                "evaluated_at": r.evaluated_at
            })
        return {"quizzes": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/attendance")
async def get_user_attendance(user_id: int, db: Session = Depends(get_db)):
    try:
        records = db.query(Attendance).filter(Attendance.student_id == user_id).all()
        output = []
        for r in records:
            session = db.query(SessionModel).filter(SessionModel.id == r.session_id).first()
            output.append({
                "session_title": session.title if session else f"Session {r.session_id}",
                "attended": r.attended,
                "join_time": r.join_time,
                "duration_minutes": r.duration_minutes
            })
        return {"attendance": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/export")
async def export_user_report(user_id: int, report_type: str = "summary", db: Session = Depends(get_db)):
    # Implementation for individual export if needed
    pass

@router.get("/export-all")
async def export_all_reports(
    search: Optional[str] = None,
    role: Optional[str] = None,
    cohort_id: Optional[int] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        # Reusing consolidated stats logic to get data
        query = db.query(User)
        if search: query = query.filter(or_(User.username.ilike(f"%{search}%"), User.email.ilike(f"%{search}%")))
        if role: query = query.filter(User.role == role)
        if cohort_id: query = query.filter(User.cohort_id == cohort_id)
        
        users = query.all()
        data = []
        for u in users:
            # Basic stats similar to consolidated
            grades = db.query(AssignmentGrade).filter(AssignmentGrade.student_id == u.id).all()
            avg_grad = sum(g.percentage for g in grades) / len(grades) if grades else 0
            
            quizzes = db.query(QuizResult).filter(QuizResult.student_id == u.id).all()
            avg_quiz = sum(q.percentage for q in quizzes) / len(quizzes) if quizzes else 0
            
            attn = db.query(Attendance).filter(Attendance.student_id == u.id).all()
            total_attn = len(attn)
            attended = sum(1 for a in attn if a.attended)
            attn_rate = (attended/total_attn*100) if total_attn > 0 else 0
            
            data.append({
                "Username": u.username,
                "Email": u.email,
                "Role": u.role,
                "Assignments Submitted": len(grades),
                "Avg Assignment %": round(avg_grad, 2),
                "Quizzes Attempted": len(quizzes),
                "Avg Quiz %": round(avg_quiz, 2),
                "Attendance %": round(attn_rate, 2)
            })
            
        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='User Reports')
            
        output.seek(0)
        headers = {
            'Content-Disposition': 'attachment; filename="consolidated_reports.xlsx"'
        }
        return Response(content=output.getvalue(), headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        raise HTTPException(status_code=500, detail="Export failed")
