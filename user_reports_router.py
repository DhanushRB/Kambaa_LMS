from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, desc, case
from datetime import datetime, timedelta
from typing import Optional, List
import csv
import io
from fastapi.responses import StreamingResponse

from database import (
    get_db, User, StudentLog, AdminLog, PresenterLog, MentorLog,
    Enrollment, Course, Cohort
)
from auth import get_current_admin_presenter_mentor_or_manager

# Import assignment and quiz models
try:
    from assignment_quiz_models import (
        Assignment, AssignmentSubmission, AssignmentGrade,
        Quiz, QuizAttempt, QuizResult
    )
except ImportError:
    from assignment_quiz_tables import (
        Assignment, AssignmentSubmission, AssignmentGrade,
        Quiz, QuizAttempt, QuizResult
    )

from cohort_specific_models import CohortAttendance

router = APIRouter(prefix="/user-reports", tags=["User Reports"])

@router.get("/users")
async def get_users_list(
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    cohort_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get list of all users with basic info for selection"""
    try:
        query = db.query(User)
        
        # Apply filters
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    User.username.ilike(search_term),
                    User.email.ilike(search_term)
                )
            )
        
        if role:
            query = query.filter(User.role == role)
        
        if cohort_id:
            query = query.filter(User.cohort_id == cohort_id)
        
        # Get total count
        total = query.count()
        
        # Pagination
        offset = (page - 1) * limit
        users = query.offset(offset).limit(limit).all()
        
        # Format response
        users_list = []
        for user in users:
            cohort_name = None
            if user.cohort_id:
                cohort = db.query(Cohort).filter(Cohort.id == user.cohort_id).first()
                cohort_name = cohort.name if cohort else None
            
            users_list.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "user_type": user.user_type,
                "cohort_id": user.cohort_id,
                "cohort_name": cohort_name,
                "college": user.college,
                "department": user.department,
                "created_at": user.created_at.isoformat() + "Z" if user.created_at else None
            })
        
        return {
            "users": users_list,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch users: {str(e)}")

@router.get("/{user_id}/summary")
async def get_user_summary(
    user_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get comprehensive summary for a specific user"""
    try:
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get cohort info
        cohort_name = None
        if user.cohort_id:
            cohort = db.query(Cohort).filter(Cohort.id == user.cohort_id).first()
            cohort_name = cohort.name if cohort else None
        
        # Get activity count
        activity_count = db.query(StudentLog).filter(StudentLog.student_id == user_id).count()
        
        # Get last login
        last_login = db.query(StudentLog).filter(
            StudentLog.student_id == user_id,
            StudentLog.action_type == "LOGIN"
        ).order_by(desc(StudentLog.timestamp)).first()
        
        # Get enrollment stats
        enrollments_count = db.query(Enrollment).filter(Enrollment.student_id == user_id).count()
        
        # Get assignment stats
        total_assignments = db.query(AssignmentSubmission).filter(
            AssignmentSubmission.student_id == user_id
        ).count()
        
        graded_assignments = db.query(AssignmentGrade).filter(
            AssignmentGrade.student_id == user_id
        ).count()
        
        avg_assignment_score = db.query(func.avg(AssignmentGrade.percentage)).filter(
            AssignmentGrade.student_id == user_id
        ).scalar() or 0
        
        # Get quiz stats
        total_quizzes = db.query(QuizAttempt).filter(
            QuizAttempt.student_id == user_id
        ).count()
        
        avg_quiz_score = db.query(func.avg(QuizResult.percentage)).filter(
            QuizResult.student_id == user_id
        ).scalar() or 0
        
        # Get attendance stats
        total_sessions = db.query(CohortAttendance).filter(
            CohortAttendance.student_id == user_id
        ).count()
        
        attended_sessions = db.query(CohortAttendance).filter(
            CohortAttendance.student_id == user_id,
            CohortAttendance.attended == True
        ).count()
        
        attendance_rate = (attended_sessions / total_sessions * 100) if total_sessions > 0 else 0
        
        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "user_type": user.user_type,
                "college": user.college,
                "department": user.department,
                "year": user.year,
                "cohort_id": user.cohort_id,
                "cohort_name": cohort_name,
                "github_link": user.github_link,
                "created_at": user.created_at.isoformat() + "Z" if user.created_at else None
            },
            "stats": {
                "total_activities": activity_count,
                "last_login": last_login.timestamp.isoformat() + "Z" if last_login else None,
                "enrollments_count": enrollments_count,
                "assignments": {
                    "total_submitted": total_assignments,
                    "graded": graded_assignments,
                    "average_score": round(avg_assignment_score, 2)
                },
                "quizzes": {
                    "total_attempted": total_quizzes,
                    "average_score": round(avg_quiz_score, 2)
                },
                "attendance": {
                    "total_sessions": total_sessions,
                    "attended": attended_sessions,
                    "attendance_rate": round(attendance_rate, 2)
                }
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch user summary: {str(e)}")

@router.get("/{user_id}/activities")
async def get_user_activities(
    user_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get detailed activity log for specific user"""
    try:
        query = db.query(StudentLog).filter(StudentLog.student_id == user_id)
        
        # Apply filters
        if date_from:
            date_from_dt = datetime.fromisoformat(date_from)
            query = query.filter(StudentLog.timestamp >= date_from_dt)
        
        if date_to:
            date_to_dt = datetime.fromisoformat(date_to)
            query = query.filter(StudentLog.timestamp <= date_to_dt)
        
        if action_type:
            query = query.filter(StudentLog.action_type == action_type)
        
        if resource_type:
            query = query.filter(StudentLog.resource_type == resource_type)
        
        # Get total count
        total = query.count()
        
        # Pagination and ordering
        offset = (page - 1) * limit
        activities = query.order_by(desc(StudentLog.timestamp)).offset(offset).limit(limit).all()
        
        # Format response
        activities_list = [{
            "id": log.id,
            "action_type": log.action_type,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else None
        } for log in activities]
        
        return {
            "activities": activities_list,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch activities: {str(e)}")

@router.get("/{user_id}/enrollments")
async def get_user_enrollments(
    user_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get all course enrollments for user"""
    try:
        enrollments = db.query(Enrollment).filter(Enrollment.student_id == user_id).all()
        
        enrollments_list = []
        for enrollment in enrollments:
            course = db.query(Course).filter(Course.id == enrollment.course_id).first()
            
            enrollments_list.append({
                "id": enrollment.id,
                "course_id": enrollment.course_id,
                "course_title": course.title if course else "Unknown",
                "enrolled_at": enrollment.enrolled_at.isoformat() + "Z" if enrollment.enrolled_at else None,
                "progress_percentage": enrollment.progress if enrollment.progress else 0,
                "completed": enrollment.progress >= 100 if enrollment.progress else False,
                "completed_at": None  # Not tracked in current schema
            })
        
        return {"enrollments": enrollments_list}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch enrollments: {str(e)}")

@router.get("/{user_id}/assignments")
async def get_user_assignments(
    user_id: int,
    course_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get all assignment submissions for user"""
    try:
        query = db.query(AssignmentSubmission).filter(AssignmentSubmission.student_id == user_id)
        
        submissions = query.all()
        
        assignments_list = []
        for submission in submissions:
            assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
            grade = db.query(AssignmentGrade).filter(
                AssignmentGrade.submission_id == submission.id
            ).first()
            
            # Filter by course if specified
            if course_id and assignment:
                # Get session to find course
                from database import Session as SessionModel
                session = db.query(SessionModel).filter(SessionModel.id == assignment.session_id).first()
                if not session or session.module.course_id != course_id:
                    continue
            
            # Filter by status if specified
            if status:
                if status == "graded" and not grade:
                    continue
                elif status == "submitted" and grade:
                    continue
                elif status == "pending" and submission:
                    continue
            
            assignments_list.append({
                "id": submission.id,
                "assignment_id": assignment.id if assignment else None,
                "assignment_title": assignment.title if assignment else "Unknown",
                "submitted_at": submission.submitted_at.isoformat() + "Z" if submission.submitted_at else None,
                "status": submission.status.value if submission.status else None,
                "grade": {
                    "marks_obtained": grade.marks_obtained,
                    "total_marks": grade.total_marks,
                    "percentage": grade.percentage,
                    "feedback": grade.feedback
                } if grade else None
            })
        
        return {"assignments": assignments_list}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch assignments: {str(e)}")

@router.get("/{user_id}/quizzes")
async def get_user_quizzes(
    user_id: int,
    course_id: Optional[int] = Query(None),
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get all quiz attempts for user"""
    try:
        query = db.query(QuizAttempt).filter(QuizAttempt.student_id == user_id)
        
        attempts = query.all()
        
        quizzes_list = []
        for attempt in attempts:
            quiz = db.query(Quiz).filter(Quiz.id == attempt.quiz_id).first()
            result = db.query(QuizResult).filter(QuizResult.attempt_id == attempt.id).first()
            
            quizzes_list.append({
                "id": attempt.id,
                "quiz_id": quiz.id if quiz else None,
                "quiz_title": quiz.title if quiz else "Unknown",
                "started_at": attempt.started_at.isoformat() + "Z" if attempt.started_at else None,
                "submitted_at": attempt.submitted_at.isoformat() + "Z" if attempt.submitted_at else None,
                "status": attempt.status.value if attempt.status else None,
                "result": {
                    "marks_obtained": result.marks_obtained,
                    "total_marks": result.total_marks,
                    "percentage": result.percentage,
                    "grade": result.grade
                } if result else None
            })
        
        return {"quizzes": quizzes_list}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch quizzes: {str(e)}")

@router.get("/{user_id}/attendance")
async def get_user_attendance(
    user_id: int,
    course_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get attendance records for user"""
    try:
        query = db.query(CohortAttendance).filter(CohortAttendance.student_id == user_id)
        
        # Apply filters
        if date_from:
            date_from_dt = datetime.fromisoformat(date_from)
            query = query.filter(CohortAttendance.created_at >= date_from_dt)
        
        if date_to:
            date_to_dt = datetime.fromisoformat(date_to)
            query = query.filter(CohortAttendance.created_at <= date_to_dt)
        
        attendance_records = query.all()
        
        attendance_list = []
        for record in attendance_records:
            from cohort_specific_models import CohortCourseSession
            session = db.query(CohortCourseSession).filter(CohortCourseSession.id == record.session_id).first()
            
            # Filter by course if specified (skip for now as cohort sessions don't have direct course_id)
            # if course_id and session:
            #     if session.module.course_id != course_id:
            #         continue
            
            attendance_list.append({
                "id": record.id,
                "session_id": record.session_id,
                "session_title": session.title if session else "Unknown",
                "status": "present" if record.attended else "absent",
                "marked_at": record.created_at.isoformat() + "Z" if record.created_at else None
            })
        
        return {"attendance": attendance_list}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch attendance: {str(e)}")

@router.get("/{user_id}/export")
async def export_user_report(
    user_id: int,
    report_type: str = Query("summary", regex="^(summary|activities|enrollments|assignments|quizzes|attendance)$"),
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Export user report as CSV"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        if report_type == "summary":
            # Get summary data
            summary_data = await get_user_summary(user_id, current_user, db)
            
            writer.writerow(["User Activity Report - Summary"])
            writer.writerow([])
            writer.writerow(["User Information"])
            writer.writerow(["Username", user.username])
            writer.writerow(["Email", user.email])
            writer.writerow(["Role", user.role])
            writer.writerow(["College", user.college])
            writer.writerow(["Department", user.department])
            writer.writerow([])
            writer.writerow(["Activity Statistics"])
            writer.writerow(["Total Activities", summary_data["stats"]["total_activities"]])
            writer.writerow(["Enrollments", summary_data["stats"]["enrollments_count"]])
            writer.writerow(["Assignments Submitted", summary_data["stats"]["assignments"]["total_submitted"]])
            writer.writerow(["Average Assignment Score", f"{summary_data['stats']['assignments']['average_score']}%"])
            writer.writerow(["Quizzes Attempted", summary_data["stats"]["quizzes"]["total_attempted"]])
            writer.writerow(["Average Quiz Score", f"{summary_data['stats']['quizzes']['average_score']}%"])
            writer.writerow(["Attendance Rate", f"{summary_data['stats']['attendance']['attendance_rate']}%"])
        
        elif report_type == "activities":
            activities_data = await get_user_activities(user_id, None, None, None, None, 1, 1000, current_user, db)
            
            writer.writerow(["Timestamp", "Action Type", "Resource Type", "Resource ID", "Details", "IP Address"])
            for activity in activities_data["activities"]:
                writer.writerow([
                    activity["timestamp"],
                    activity["action_type"],
                    activity["resource_type"],
                    activity["resource_id"],
                    activity["details"],
                    activity["ip_address"]
                ])
        
        # Generate filename
        filename = f"user_report_{user.username}_{report_type}_{datetime.now().strftime('%Y%m%d')}.csv"
        
        # Return as streaming response
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export report: {str(e)}")
@router.get("/export-all")
async def export_all_activities(
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    cohort_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None, regex="^(activities|enrollments|assignments|quizzes|attendance)$"),
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Export user reports filtered by category for all matching users"""
    try:
        # 1. Get filtered users
        user_query = db.query(User)
        if search:
            search_term = f"%{search}%"
            user_query = user_query.filter(or_(User.username.ilike(search_term), User.email.ilike(search_term)))
        if role:
            user_query = user_query.filter(User.role == role)
        if cohort_id:
            user_query = user_query.filter(User.cohort_id == cohort_id)
        
        users = user_query.all()

        output = io.StringIO()
        writer = csv.writer(output)
        
        # Headers matching user request + Category
        writer.writerow([
            "Timestamp", "User ID", "Username", "Email", "Category", 
            "Action/Item", "Resource Type", "Resource ID", "Details/Status", "IP Address"
        ])

        for user in users:
            user_id = user.id
            username = user.username
            email = user.email
            
            # --- CATEGORY: ACTIVITIES ---
            if not category or category == "activities":
                logs = db.query(StudentLog).filter(StudentLog.student_id == user_id).order_by(desc(StudentLog.timestamp)).all()
                for log in logs:
                    writer.writerow([
                        log.timestamp.isoformat() + "Z" if log.timestamp else "",
                        user_id, username, email, "Activity",
                        log.action_type, log.resource_type or "", log.resource_id or "",
                        log.details or "", log.ip_address or ""
                    ])

            # --- CATEGORY: ENROLLMENTS ---
            if not category or category == "enrollments":
                enrollments = db.query(Enrollment).filter(Enrollment.student_id == user_id).all()
                for enr in enrollments:
                    course = db.query(Course).filter(Course.id == enr.course_id).first()
                    writer.writerow([
                        enr.enrolled_at.isoformat() + "Z" if enr.enrolled_at else "",
                        user_id, username, email, "Enrollment",
                        course.title if course else "Unknown Course", "Course", enr.course_id,
                        f"Progress: {enr.progress}%", ""
                    ])

            # --- CATEGORY: ASSIGNMENTS ---
            if not category or category == "assignments":
                submissions = db.query(AssignmentSubmission).filter(AssignmentSubmission.student_id == user_id).all()
                for sub in submissions:
                    assign = db.query(Assignment).filter(Assignment.id == sub.assignment_id).first()
                    grade = db.query(AssignmentGrade).filter(AssignmentGrade.submission_id == sub.id).first()
                    grade_str = f"Grade: {grade.marks_obtained}/{grade.total_marks} ({grade.percentage}%)" if grade else "Not Graded"
                    writer.writerow([
                        sub.submitted_at.isoformat() + "Z" if sub.submitted_at else "",
                        user_id, username, email, "Assignment",
                        assign.title if assign else "Unknown Assignment", "Assignment", sub.assignment_id,
                        f"Status: {sub.status.value if sub.status else 'Submitted'}, {grade_str}", ""
                    ])

            # --- CATEGORY: QUIZZES ---
            if not category or category == "quizzes":
                attempts = db.query(QuizAttempt).filter(QuizAttempt.student_id == user_id).all()
                for att in attempts:
                    quiz = db.query(Quiz).filter(Quiz.id == att.quiz_id).first()
                    res = db.query(QuizResult).filter(QuizResult.attempt_id == att.id).first()
                    res_str = f"Score: {res.marks_obtained}/{res.total_marks} ({res.percentage}%)" if res else "No Result"
                    writer.writerow([
                        att.submitted_at.isoformat() + "Z" if att.submitted_at else (att.started_at.isoformat() + "Z" if att.started_at else ""),
                        user_id, username, email, "Quiz",
                        quiz.title if quiz else "Unknown Quiz", "Quiz", att.quiz_id,
                        f"Status: {att.status.value if att.status else 'N/A'}, {res_str}", ""
                    ])

            # --- CATEGORY: ATTENDANCE ---
            if not category or category == "attendance":
                attendance_recs = db.query(CohortAttendance).filter(CohortAttendance.student_id == user_id).all()
                from cohort_specific_models import CohortCourseSession
                for rec in attendance_recs:
                    session = db.query(CohortCourseSession).filter(CohortCourseSession.id == rec.session_id).first()
                    writer.writerow([
                        rec.created_at.isoformat() + "Z" if rec.created_at else "",
                        user_id, username, email, "Attendance",
                        session.title if session else "Unknown Session", "Session", rec.session_id,
                        "Present" if rec.attended else "Absent", ""
                    ])

            # --- CATEGORY: OVERVIEW (Aggregated Stats) ---
            if not category:
                summary = await get_user_summary(user_id, current_user, db)
                stats = summary["stats"]
                writer.writerow([
                    datetime.utcnow().isoformat() + "Z",
                    user_id, username, email, "Overview",
                    "Summary Stats", "", "",
                    f"Total Activities: {stats['total_activities']}, Enrollments: {stats['enrollments_count']}, "
                    f"Avg Assignment: {stats['assignments']['average_score']}%, Attendance Rate: {stats['attendance']['attendance_rate']}%", ""
                ])

        # Generate filename
        timestamp_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"consolidated_user_reports_{timestamp_str}.csv"
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export consolidated report: {str(e)}")

@router.get("/consolidated")
async def get_consolidated_user_stats(
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    cohort_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get consolidated statistics for all users efficiently"""
    try:
        # Base query
        query = db.query(User)
        
        # Apply filters
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    User.username.ilike(search_term),
                    User.email.ilike(search_term)
                )
            )
        
        if role:
            query = query.filter(User.role == role)
        
        if cohort_id:
            query = query.filter(User.cohort_id == cohort_id)
        
        # Get total count
        total = query.count()
        
        # Pagination
        offset = (page - 1) * limit
        users = query.offset(offset).limit(limit).all()
        
        # Collect user IDs for batch fetching
        user_ids = [user.id for user in users]
        
        if not user_ids:
            return {
                "users": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "total_pages": 0
            }

        # --- Batch Fetch Stats ---
        
        # 1. Activity Counts (StudentLog)
        activity_counts = db.query(
            StudentLog.student_id, func.count(StudentLog.id)
        ).filter(StudentLog.student_id.in_(user_ids)).group_by(StudentLog.student_id).all()
        activity_map = {uid: count for uid, count in activity_counts}

        # 2. Assignments (Submitted count, Avg Score)
        assignment_stats = db.query(
            AssignmentSubmission.student_id,
            func.count(AssignmentSubmission.id).label('submitted'),
            func.avg(AssignmentGrade.percentage).label('avg_score')
        ).outerjoin(
            AssignmentGrade, AssignmentGrade.submission_id == AssignmentSubmission.id
        ).filter(
            AssignmentSubmission.student_id.in_(user_ids)
        ).group_by(AssignmentSubmission.student_id).all()
        assignment_map = {
            uid: {'submitted': submitted, 'avg': round(avg, 2) if avg else 0} 
            for uid, submitted, avg in assignment_stats
        }

        # 3. Quizzes (Attempted count, Avg Score)
        quiz_stats = db.query(
            QuizAttempt.student_id,
            func.count(QuizAttempt.id).label('attempted'),
            func.avg(QuizResult.percentage).label('avg_score')
        ).outerjoin(
            QuizResult, QuizResult.attempt_id == QuizAttempt.id
        ).filter(
            QuizAttempt.student_id.in_(user_ids)
        ).group_by(QuizAttempt.student_id).all()
        quiz_map = {
            uid: {'attempted': attempted, 'avg': round(avg, 2) if avg else 0}
            for uid, attempted, avg in quiz_stats
        }

        # 4. Attendance (Rate)
        # Fetch total sessions and attended sessions per student
        attendance_stats = db.query(
            CohortAttendance.student_id,
            func.count(CohortAttendance.id).label('total'),
            func.sum(case((CohortAttendance.attended == True, 1), else_=0)).label('attended')
        ).filter(
            CohortAttendance.student_id.in_(user_ids)
        ).group_by(CohortAttendance.student_id).all()
        attendance_map = {
            uid: {
                'rate': round((attended / total * 100), 2) if total > 0 else 0
            }
            for uid, total, attended in attendance_stats
        }

        # 5. Cohort Names
        cohort_ids = {user.cohort_id for user in users if user.cohort_id}
        cohorts = db.query(Cohort).filter(Cohort.id.in_(cohort_ids)).all()
        cohort_map = {c.id: c.name for c in cohorts}

        # Construct Result
        consolidated_list = []
        for user in users:
            uid = user.id
            stats = {
                "id": uid,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "cohort_name": cohort_map.get(user.cohort_id) if user.cohort_id else None,
                "activities_count": activity_map.get(uid, 0),
                "assignments_submitted": assignment_map.get(uid, {}).get('submitted', 0),
                "assignments_avg": assignment_map.get(uid, {}).get('avg', 0),
                "quizzes_attempted": quiz_map.get(uid, {}).get('attempted', 0),
                "quizzes_avg": quiz_map.get(uid, {}).get('avg', 0),
                "attendance_rate": attendance_map.get(uid, {}).get('rate', 0)
            }
            consolidated_list.append(stats)
            
        return {
            "users": consolidated_list,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit
        }

    except Exception as e:
        print(f"Error in consolidated stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch consolidated stats: {str(e)}")
