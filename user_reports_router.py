from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from typing import List, Optional
from datetime import datetime, timedelta
import io
import pandas as pd
from database import get_db, User, Cohort, Enrollment, Attendance, Session as SessionModel, Module, Course, AdminLog, StudentLog, StudentSessionStatus, CohortCourse
from cohort_specific_models import CohortCourseSession, CohortAttendance, CohortSpecificCourse, CohortSpecificEnrollment
from assignment_quiz_models import Assignment, AssignmentSubmission, AssignmentGrade, Quiz, QuizAttempt, QuizResult
from auth import get_current_user_any_role
import logging

router = APIRouter(tags=["user_reports"])
logger = logging.getLogger(__name__)

def calculate_live_progress(db: Session, student_id: int, course_id: int, course_type: str = "global"):
    """Calculate course progress by averaging session progress percentages"""
    try:
        from database import Module, Session as SessionModel
        from cohort_specific_models import CohortCourseModule, CohortCourseSession
        
        if course_type == "cohort":
            modules = db.query(CohortCourseModule).filter(CohortCourseModule.course_id == course_id).all()
            module_ids = [m.id for m in modules]
            sessions = db.query(CohortCourseSession).filter(CohortCourseSession.module_id.in_(module_ids)).all() if module_ids else []
            s_type = "cohort"
        else:
            modules = db.query(Module).filter(Module.course_id == course_id).all()
            module_ids = [m.id for m in modules]
            sessions = db.query(SessionModel).filter(SessionModel.module_id.in_(module_ids)).all() if module_ids else []
            s_type = "global"
            
        if not sessions:
            return 0
            
        session_ids = [s.id for s in sessions]
        statuses = db.query(StudentSessionStatus).filter(
            StudentSessionStatus.student_id == student_id,
            StudentSessionStatus.session_id.in_(session_ids),
            StudentSessionStatus.session_type == s_type
        ).all()
        
        if not statuses:
            return 0
            
        # Group by session_id to handle duplicates, taking the max progress
        session_progress = {}
        for s in statuses:
            if s.session_id not in session_progress or (s.progress_percentage or 0) > session_progress[s.session_id]:
                session_progress[s.session_id] = s.progress_percentage or 0
                
        total_progress = sum(session_progress.values())
        return round(total_progress / len(sessions), 1)
    except Exception as e:
        logger.error(f"Error calculating live progress: {str(e)}")
        return 0

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
            # Attendance stats - check both Attendance table and Session Status
            attendance_records = db.query(Attendance).filter(Attendance.student_id == user.id).all()
            total_attendance = len(attendance_records)
            attended_count = sum(1 for a in attendance_records if a.attended)
            
            # Fallback to StudentSessionStatus if no live attendance records
            if total_attendance == 0:
                session_statuses = db.query(StudentSessionStatus).filter(StudentSessionStatus.student_id == user.id).all()
                if session_statuses:
                    attendance_rate = sum(s.progress_percentage for s in session_statuses) / len(session_statuses)
                else:
                    attendance_rate = 0
            else:
                attendance_rate = (attended_count / total_attendance * 100)
            
            # Assignment stats
            submissions = db.query(AssignmentSubmission).filter(AssignmentSubmission.student_id == user.id).all()
            assignment_grades = db.query(AssignmentGrade).filter(AssignmentGrade.student_id == user.id).all()
            avg_assignment = sum(g.percentage for g in assignment_grades) / len(assignment_grades) if assignment_grades else 0
            
            # Quiz stats
            attempts = db.query(QuizAttempt).filter(QuizAttempt.student_id == user.id).all()
            quiz_results = db.query(QuizResult).filter(QuizResult.student_id == user.id).all()
            avg_quiz = sum(r.percentage for r in quiz_results) / len(quiz_results) if quiz_results else 0
            
            # Activities Count based on role
            if user.role in ['Student', 'Faculty']:
                activities_count = db.query(StudentLog).filter(StudentLog.student_id == user.id).count()
            else:
                activities_count = db.query(AdminLog).filter(AdminLog.admin_username == user.username).count()
            
            cohort_name = db.query(Cohort.name).filter(Cohort.id == user.cohort_id).scalar()
            
            results.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "cohort_name": cohort_name,
                "activities_count": activities_count,
                "assignments_submitted": len(submissions),
                "assignments_avg": round(avg_assignment, 2),
                "quizzes_attempted": len(attempts),
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
        
        cohort_name = db.query(Cohort.name).filter(Cohort.id == user.cohort_id).scalar()
        
        # Enrollment count (Global + Cohort Assigned + Cohort Specific)
        global_enrolled = db.query(Enrollment.course_id).filter(Enrollment.student_id == user_id).all()
        global_ids = {e.course_id for e in global_enrolled}
        
        cohort_assigned = db.query(CohortCourse.course_id).filter(CohortCourse.cohort_id == user.cohort_id).all()
        cohort_global_ids = {c.course_id for c in cohort_assigned}
        
        cohort_specific = db.query(CohortSpecificCourse).filter(CohortSpecificCourse.cohort_id == user.cohort_id).count()
        
        enrollments_count = len(global_ids | cohort_global_ids) + cohort_specific
        
        # Assignment stats
        submissions = db.query(AssignmentSubmission).filter(AssignmentSubmission.student_id == user_id).all()
        submission_ids = [s.id for s in submissions]
        graded_count = db.query(AssignmentGrade).filter(AssignmentGrade.submission_id.in_(submission_ids)).count() if submission_ids else 0
        assignment_grades = db.query(AssignmentGrade).filter(AssignmentGrade.student_id == user_id).all()
        avg_assignment = sum(g.percentage for g in assignment_grades) / len(assignment_grades) if assignment_grades else 0
        
        # Quiz stats
        attempts = db.query(QuizAttempt).filter(QuizAttempt.student_id == user_id).all()
        quiz_results = db.query(QuizResult).filter(QuizResult.student_id == user_id).all()
        avg_quiz = sum(r.percentage for r in quiz_results) / len(quiz_results) if quiz_results else 0
        
        # Attendance stats
        attendance_records = db.query(Attendance).filter(Attendance.student_id == user_id).all()
        total_attendance = len(attendance_records)
        attended_count = sum(1 for a in attendance_records if a.attended)
        
        if total_attendance == 0:
            session_statuses = db.query(StudentSessionStatus).filter(StudentSessionStatus.student_id == user_id).all()
            if session_statuses:
                attendance_rate = sum(s.progress_percentage for s in session_statuses) / len(session_statuses)
            else:
                attendance_rate = 0
        else:
            attendance_rate = (attended_count / total_attendance * 100)
            
        # Activity count
        if user.role in ['Student', 'Faculty']:
            activities_count = db.query(StudentLog).filter(StudentLog.student_id == user_id).count()
        else:
            activities_count = db.query(AdminLog).filter(AdminLog.admin_username == user.username).count()
        
        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "college": user.college,
                "department": user.department,
                "year": user.year,
                "github_link": user.github_link,
                "cohort_name": cohort_name,
                "created_at": user.created_at
            },
            "stats": {
                "total_activities": activities_count,
                "enrollments_count": enrollments_count,
                "assignments": {
                    "total_submitted": len(submissions),
                    "graded": graded_count,
                    "average_score": round(avg_assignment, 2)
                },
                "quizzes": {
                    "total_attempted": len(attempts),
                    "average_score": round(avg_quiz, 2)
                },
                "attendance": {
                    "total_sessions": total_attendance,
                    "attended": attended_count,
                    "attendance_rate": round(attendance_rate, 2)
                }
            }
        }
    except Exception as e:
        logger.error(f"Error fetching user summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch summary")

@router.get("/{user_id}/activities")
async def get_user_activities(user_id: int, page: int = 1, limit: int = 50, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user: return {"activities": [], "total": 0}
        
        if user.role in ['Student', 'Faculty']:
            query = db.query(StudentLog).filter(StudentLog.student_id == user_id).order_by(StudentLog.timestamp.desc())
        else:
            query = db.query(AdminLog).filter(AdminLog.admin_username == user.username).order_by(AdminLog.timestamp.desc())
            
        total = query.count()
        logs = query.offset((page - 1) * limit).limit(limit).all()
        activities = [{
            "id": log.id,
            "action": log.action_type,
            "resource": log.resource_type,
            "details": log.details,
            "timestamp": log.timestamp
        } for log in logs]
            
        return {"activities": activities, "total": total}
    except Exception as e:
        logger.error(f"Error fetching activities: {str(e)}")
        return {"activities": [], "total": 0}

@router.get("/{user_id}/enrollments")
async def get_user_enrollments(user_id: int, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user: return {"enrollments": []}
        
        output = []
        seen_global_ids = set()
        
        # 1. Direct Global Enrollments
        enrollments = db.query(Enrollment).filter(Enrollment.student_id == user_id).all()
        for e in enrollments:
            course = db.query(Course).filter(Course.id == e.course_id).first()
            seen_global_ids.add(e.course_id)
            
            # Calculate live progress
            prog_pct = calculate_live_progress(db, user_id, e.course_id, "global")
            
            output.append({
                "id": f"global_{e.id}",
                "course_title": course.title if course else "Unknown Global Course",
                "enrolled_at": e.enrolled_at,
                "progress_percentage": prog_pct,
                "completed": prog_pct >= 100,
                "status": e.payment_status,
                "type": "Global"
            })
            
        # 2. Cohort-Assigned Global Courses (if not already in #1)
        if user.cohort_id:
            cohort_courses = db.query(CohortCourse).filter(CohortCourse.cohort_id == user.cohort_id).all()
            for cc in cohort_courses:
                if cc.course_id not in seen_global_ids:
                    course = db.query(Course).filter(Course.id == cc.course_id).first()
                    
                    # Calculate live progress
                    prog_pct = calculate_live_progress(db, user_id, cc.course_id, "global")
                    
                    output.append({
                        "id": f"cohort_assigned_{cc.id}",
                        "course_title": course.title if course else f"Course {cc.course_id}",
                        "enrolled_at": cc.assigned_at,
                        "progress_percentage": prog_pct,
                        "completed": prog_pct >= 100,
                        "status": "Assigned",
                        "type": "Cohort (Global)"
                    })
                    
        # 3. Cohort-Specific Courses
        if user.cohort_id:
            cohort_specific = db.query(CohortSpecificCourse).filter(CohortSpecificCourse.cohort_id == user.cohort_id).all()
            for csc in cohort_specific:
                # Calculate live progress
                prog_pct = calculate_live_progress(db, user_id, csc.id, "cohort")
                
                # Check for progress record (for enroll date)
                prog_rec = db.query(CohortSpecificEnrollment).filter(
                    CohortSpecificEnrollment.student_id == user_id,
                    CohortSpecificEnrollment.course_id == csc.id
                ).first()
                
                output.append({
                    "id": f"cohort_spec_{csc.id}",
                    "course_title": csc.title,
                    "enrolled_at": prog_rec.enrolled_at if prog_rec else csc.created_at,
                    "progress_percentage": prog_pct,
                    "completed": prog_pct >= 100,
                    "status": "Active",
                    "type": "Cohort Specific"
                })
                
        return {"enrollments": output}
    except Exception as e:
        logger.error(f"Error fetching enrollments: {str(e)}")
        return {"enrollments": []}

@router.get("/{user_id}/assignments")
async def get_user_assignments(user_id: int, db: Session = Depends(get_db)):
    try:
        submissions = db.query(AssignmentSubmission).filter(AssignmentSubmission.student_id == user_id).all()
        results = []
        for s in submissions:
            assignment = db.query(Assignment).filter(Assignment.id == s.assignment_id).first()
            grade = db.query(AssignmentGrade).filter(AssignmentGrade.submission_id == s.id).first()
            results.append({
                "id": s.id,
                "assignment_title": assignment.title if assignment else "Unknown Assignment",
                "submitted_at": s.submitted_at,
                "status": s.status.value if hasattr(s.status, 'value') else str(s.status),
                "grade": {
                    "marks_obtained": grade.marks_obtained,
                    "total_marks": grade.total_marks,
                    "percentage": grade.percentage,
                    "feedback": grade.feedback
                } if grade else None
            })
        return {"assignments": results}
    except Exception as e:
        logger.error(f"Error fetching assignments: {str(e)}")
        return {"assignments": []}

@router.get("/{user_id}/quizzes")
async def get_user_quizzes(user_id: int, db: Session = Depends(get_db)):
    try:
        attempts = db.query(QuizAttempt).filter(QuizAttempt.student_id == user_id).all()
        output = []
        for a in attempts:
            quiz = db.query(Quiz).filter(Quiz.id == a.quiz_id).first()
            result = db.query(QuizResult).filter(QuizResult.attempt_id == a.id).first()
            output.append({
                "id": a.id,
                "quiz_title": quiz.title if quiz else "Unknown Quiz",
                "status": a.status.value if hasattr(a.status, 'value') else str(a.status),
                "started_at": a.started_at,
                "submitted_at": a.submitted_at,
                "result": {
                    "marks_obtained": result.marks_obtained,
                    "total_marks": result.total_marks,
                    "percentage": result.percentage,
                    "grade": result.grade
                } if result else None
            })
        return {"quizzes": output}
    except Exception as e:
        logger.error(f"Error fetching quizzes: {str(e)}")
        return {"quizzes": []}

@router.get("/{user_id}/attendance")
async def get_user_attendance(user_id: int, db: Session = Depends(get_db)):
    try:
        # Get formal attendance records (Global)
        global_records = db.query(Attendance).filter(Attendance.student_id == user_id).all()
        
        # Get formal attendance records (Cohort-specific)
        cohort_records = db.query(CohortAttendance).filter(CohortAttendance.student_id == user_id).all()
        
        # Get session statuses (fallback/additional info)
        session_statuses = db.query(StudentSessionStatus).filter(StudentSessionStatus.student_id == user_id).all()
        
        output = []
        # Track which sessions we've already covered via formal attendance
        # Format: (session_id, session_type)
        covered_sessions = set()
        
        # Process global attendance
        for r in global_records:
            session = db.query(SessionModel).filter(SessionModel.id == r.session_id).first()
            covered_sessions.add((r.session_id, "global"))
            output.append({
                "id": f"attn_global_{r.id}",
                "session_title": session.title if session else f"Session {r.session_id}",
                "marked_at": r.join_time or r.created_at,
                "status": "present" if r.attended else "absent",
                "duration_minutes": r.duration_minutes,
                "type": "Live Session (Global)"
            })
            
        # Process cohort attendance
        for r in cohort_records:
            session = db.query(CohortCourseSession).filter(CohortCourseSession.id == r.session_id).first()
            covered_sessions.add((r.session_id, "cohort"))
            output.append({
                "id": f"attn_cohort_{r.id}",
                "session_title": session.title if session else f"Session {r.session_id}",
                "marked_at": r.first_join_time or r.created_at,
                "status": "present" if r.attended else "absent",
                "duration_minutes": r.total_duration_minutes,
                "type": "Live Session (Cohort)"
            })
            
        # Add session statuses for sessions not covered by formal attendance
        for s in session_statuses:
            if (s.session_id, s.session_type) not in covered_sessions:
                if s.session_type == "cohort":
                    session = db.query(CohortCourseSession).filter(CohortCourseSession.id == s.session_id).first()
                else:
                    session = db.query(SessionModel).filter(SessionModel.id == s.session_id).first()
                
                output.append({
                    "id": f"status_{s.id}",
                    "session_title": session.title if session else f"Session {s.session_id}",
                    "marked_at": s.completed_at or s.started_at or datetime.utcnow(),
                    "status": "present" if s.status == "Completed" else "absent" if s.status == "Not Attended" else "in_progress",
                    "duration_minutes": 0,
                    "progress": s.progress_percentage,
                    "type": f"Self-paced ({s.session_type.capitalize()})"
                })
                
        # Sort by date
        output.sort(key=lambda x: x["marked_at"] if x["marked_at"] else datetime.min, reverse=True)
            
        return {"attendance": output}
    except Exception as e:
        logger.error(f"Error fetching attendance: {str(e)}")
        return {"attendance": []}

@router.get("/{user_id}/export")
async def export_user_report(user_id: int, report_type: str = "summary", db: Session = Depends(get_db)):
    # Legacy export endpoint placeholder
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
        query = db.query(User)
        if search: query = query.filter(or_(User.username.ilike(f"%{search}%"), User.email.ilike(f"%{search}%")))
        if role: query = query.filter(User.role == role)
        if cohort_id: query = query.filter(User.cohort_id == cohort_id)
        
        users = query.all()
        data = []
        for u in users:
            grades = db.query(AssignmentGrade).filter(AssignmentGrade.student_id == u.id).all()
            avg_grad = sum(g.percentage for g in grades) / len(grades) if grades else 0
            
            quizzes = db.query(QuizResult).filter(QuizResult.student_id == u.id).all()
            avg_quiz = sum(q.percentage for q in quizzes) / len(quizzes) if quizzes else 0
            
            attn = db.query(Attendance).filter(Attendance.student_id == u.id).all()
            total_attn = len(attn)
            attended = sum(1 for a in attn if a.attended)
            
            if total_attn == 0:
                ss = db.query(StudentSessionStatus).filter(StudentSessionStatus.student_id == u.id).all()
                attn_rate = sum(s.progress_percentage for s in ss) / len(ss) if ss else 0
            else:
                attn_rate = (attended/total_attn*100)
            
            if u.role in ['Student', 'Faculty']:
                act = db.query(StudentLog).filter(StudentLog.student_id == u.id).count()
            else:
                act = db.query(AdminLog).filter(AdminLog.admin_username == u.username).count()
            
            data.append({
                "Username": u.username,
                "Email": u.email,
                "Role": u.role,
                "Activities": act,
                "Assignments Submitted": db.query(AssignmentSubmission).filter(AssignmentSubmission.student_id == u.id).count(),
                "Avg Assignment %": round(avg_grad, 2),
                "Quizzes Attempted": db.query(QuizAttempt).filter(QuizAttempt.student_id == u.id).count(),
                "Avg Quiz %": round(avg_quiz, 2),
                "Attendance %": round(attn_rate, 2)
            })
            
        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='User Reports')
            
        output.seek(0)
        headers = {'Content-Disposition': 'attachment; filename="consolidated_reports.xlsx"'}
        return Response(content=output.getvalue(), headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        raise HTTPException(status_code=500, detail="Export failed")
