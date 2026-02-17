from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
import pandas as pd
from io import BytesIO
import re
from datetime import timedelta

from database import get_db, User, Enrollment
from auth import get_current_admin_presenter_mentor_or_manager
from cohort_specific_models import (
    CohortSpecificCourse, 
    CohortCourseModule, 
    CohortCourseSession,
    CohortAttendance,
    CohortSpecificEnrollment
)

router = APIRouter(prefix="/cohorts", tags=["Cohort Attendance"])

class AttendanceMark(BaseModel):
    student_id: int
    attended: bool

class AttendanceSubmit(BaseModel):
    attendance: List[AttendanceMark]

@router.get("/{cohort_id}/courses/{course_id}/sessions/{session_id}/students")
async def get_session_students(
    cohort_id: int,
    course_id: int,
    session_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get list of students enrolled in the course for attendance marking"""
    try:
        # Verify session exists
        session = db.query(CohortCourseSession).filter(CohortCourseSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get all students enrolled in this cohort course
        # First check cohort_specific_enrollments
        students = db.query(User).join(
            CohortSpecificEnrollment, User.id == CohortSpecificEnrollment.student_id
        ).filter(
            CohortSpecificEnrollment.course_id == course_id
        ).all()

        # If no students in cohort_specific_enrollments, check general enrollments for this cohort
        if not students:
            students = db.query(User).join(
                Enrollment, User.id == Enrollment.student_id
            ).filter(
                Enrollment.cohort_id == cohort_id,
                Enrollment.course_id == course_id
            ).all()

        # If still no students, get all students in this cohort
        if not students:
            from database import UserCohort
            students = db.query(User).join(
                UserCohort, User.id == UserCohort.user_id
            ).filter(
                UserCohort.cohort_id == cohort_id,
                UserCohort.is_active == True
            ).all()

        # Get existing attendance for this session
        existing_attendance = db.query(CohortAttendance).filter(
            CohortAttendance.session_id == session_id
        ).all()
        attendance_map = {a.student_id: a for a in existing_attendance}

        result = []
        for student in students:
            att_record = attendance_map.get(student.id)
            
            # Derive status for display
            status = "Absent"
            if att_record:
                if att_record.attended:
                    status = "Present"
                elif att_record.total_duration_minutes > 0:
                    status = "Failed"
                else:
                    status = "Absent"
                    
            result.append({
                "id": student.id,
                "username": student.username,
                "email": student.email,
                "full_name": getattr(student, 'full_name', student.username),
                "college": student.college,
                "department": student.department,
                "attended": att_record.attended if att_record else False,
                "status": status,
                "first_join_time": att_record.first_join_time if att_record else None,
                "last_leave_time": att_record.last_leave_time if att_record else None,
                "total_duration_minutes": att_record.total_duration_minutes if att_record else 0.0
            })

        return {"students": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch students: {str(e)}")
        
@router.get("/{cohort_id}/courses/{course_id}/sessions/{session_id}")
async def get_cohort_session_details(
    cohort_id: int,
    course_id: int,
    session_id: int,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Get details of a specific cohort session"""
    try:
        session = db.query(CohortCourseSession).filter(CohortCourseSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        module = db.query(CohortCourseModule).filter(CohortCourseModule.id == session.module_id).first()
        
        return {
            "id": session.id,
            "session_number": session.session_number,
            "title": session.title,
            "description": session.description,
            "scheduled_time": session.scheduled_time,
            "duration_minutes": session.duration_minutes,
            "module_id": session.module_id,
            "module_title": module.title if module else None,
            "created_at": session.created_at
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch session details: {str(e)}")

@router.post("/{cohort_id}/courses/{course_id}/sessions/{session_id}/attendance")
async def submit_attendance(
    cohort_id: int,
    course_id: int,
    session_id: int,
    attendance_data: AttendanceSubmit,
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Submit attendance for a session"""
    try:
        # Verify session exists
        session = db.query(CohortCourseSession).filter(CohortCourseSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        for mark in attendance_data.attendance:
            # Check if record exists
            attendance = db.query(CohortAttendance).filter(
                CohortAttendance.session_id == session_id,
                CohortAttendance.student_id == mark.student_id
            ).first()

            if attendance:
                attendance.attended = mark.attended
                attendance.created_at = datetime.utcnow()
            else:
                new_attendance = CohortAttendance(
                    session_id=session_id,
                    student_id=mark.student_id,
                    attended=mark.attended
                )
                db.add(new_attendance)

        db.commit()
        return {"message": "Attendance saved successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save attendance: {str(e)}")

@router.get("/{cohort_id}/courses/{course_id}/sessions/{session_id}/attendance/export")
async def export_attendance(
    cohort_id: int,
    course_id: int,
    session_id: int,
    format: str = "excel",  # excel or csv
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Export attendance data as Excel or CSV file"""
    try:
        # Verify session exists
        session = db.query(CohortCourseSession).filter(CohortCourseSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get all students enrolled in this cohort course
        students = db.query(User).join(
            CohortSpecificEnrollment, User.id == CohortSpecificEnrollment.student_id
        ).filter(
            CohortSpecificEnrollment.course_id == course_id
        ).all()

        # If no students in cohort_specific_enrollments, check general enrollments
        if not students:
            students = db.query(User).join(
                Enrollment, User.id == Enrollment.student_id
            ).filter(
                Enrollment.cohort_id == cohort_id,
                Enrollment.course_id == course_id
            ).all()

        # If still no students, get all students in this cohort
        if not students:
            from database import UserCohort
            students = db.query(User).join(
                UserCohort, User.id == UserCohort.user_id
            ).filter(
                UserCohort.cohort_id == cohort_id,
                UserCohort.is_active == True
            ).all()

        # Get existing attendance
        existing_attendance = db.query(CohortAttendance).filter(
            CohortAttendance.session_id == session_id
        ).all()
        attendance_map = {a.student_id: a.attended for a in existing_attendance}

        # Prepare data for export
        data = []
        for student in students:
            data.append({
                "Session": session.title,
                "Student ID": student.id,
                "Name": getattr(student, 'full_name', student.username),
                "Email": student.email,
                "College": student.college or "N/A",
                "Department": student.department or "N/A",
                "Attendance Status": "Present" if attendance_map.get(student.id, False) else "Absent"
            })

        # Create DataFrame
        df = pd.DataFrame(data)

        # Generate file
        output = BytesIO()
        if format.lower() == "csv":
            df.to_csv(output, index=False)
            media_type = "text/csv"
            filename = f"attendance_session_{session_id}.csv"
        else:  # excel
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Attendance')
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"attendance_session_{session_id}.xlsx"

        output.seek(0)
        
        return StreamingResponse(
            output,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export attendance: {str(e)}")

def parse_duration_string(dur_str: str) -> float:
    """Parse duration strings like '1h 27m 29s', '46m 5s', 'hh:mm:ss', 'mm:ss' to minutes."""
    if not dur_str or not isinstance(dur_str, str):
        if isinstance(dur_str, (int, float)):
            return float(dur_str)
        return 0.0
    
    dur_str = dur_str.lower().strip()
    
    # Handle '1h 27m 29s' format
    if any(unit in dur_str for unit in ['h', 'm', 's']):
        total_minutes = 0.0
        # Hours
        h_match = re.search(r'(\d+)\s*h', dur_str)
        if h_match:
            total_minutes += int(h_match.group(1)) * 60
        # Minutes
        m_match = re.search(r'(\d+)\s*m', dur_str)
        if m_match:
            total_minutes += int(m_match.group(1))
        # Seconds
        s_match = re.search(r'(\d+)\s*s', dur_str)
        if s_match:
            total_minutes += int(s_match.group(1)) / 60
        
        if total_minutes > 0:
            return total_minutes
    
    # Handle 'hh:mm:ss' or 'mm:ss'
    if ':' in dur_str:
        parts = dur_str.split(':')
        try:
            if len(parts) == 3: # hh:mm:ss
                return int(parts[0])*60 + int(parts[1]) + int(parts[2])/60
            elif len(parts) == 2: # mm:ss
                return int(parts[0]) + int(parts[1])/60
        except ValueError:
            pass
            
    # Fallback: try removing common non-numeric chars if it's not a standard format
    try:
        clean_val = re.sub(r'[^\d.]', '', dur_str)
        if clean_val:
            return float(clean_val)
    except ValueError:
        pass
        
    return 0.0
@router.post("/{cohort_id}/courses/{course_id}/sessions/{session_id}/attendance/import")
async def import_attendance(
    cohort_id: int,
    course_id: int,
    session_id: int,
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    min_duration_minutes: Optional[int] = Query(None),
    file: UploadFile = File(...),
    current_user = Depends(get_current_admin_presenter_mentor_or_manager),
    db: Session = Depends(get_db)
):
    """Import attendance data from Excel or CSV file with optional duration analysis"""
    try:
        # Verify session exists
        session = db.query(CohortCourseSession).filter(CohortCourseSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Read the file
        contents = await file.read()
        file_ext = file.filename.split('.')[-1].lower()
        
        # Read without headers first to scan for them
        if file_ext == 'csv':
            df_raw = pd.read_csv(BytesIO(contents), header=None)
        else:
            df_raw = pd.read_excel(BytesIO(contents), header=None)

        # 1. SUMMARY EXTRACTION (Scan rows 0-10)
        summary_data = {}
        for i, row in df_raw.head(15).iterrows():
            row_vals = [str(val).strip() for val in row if pd.notna(val)]
            row_str = " ".join(row_vals).lower()
            
            if 'meeting title' in row_str and len(row_vals) >= 2:
                summary_data['title'] = row_vals[1]
            elif 'start time' in row_str and len(row_vals) >= 2:
                summary_data['start_time'] = row_vals[1]
            elif 'end time' in row_str and len(row_vals) >= 2:
                summary_data['end_time'] = row_vals[1]
            elif 'overall meeting duration' in row_str and len(row_vals) >= 2:
                summary_data['duration_str'] = row_vals[1]
                summary_data['duration_minutes'] = parse_duration_string(row_vals[1])

        # Auto-update session metadata if found
        if summary_data.get('title'):
            session.title = summary_data['title']
        if summary_data.get('duration_minutes'):
            session.duration_minutes = int(summary_data['duration_minutes'])
        if summary_data.get('start_time'):
            try:
                # Teams format often like '2/15/26, 6:12:42 PM'
                session.scheduled_time = pd.to_datetime(summary_data['start_time'])
            except: pass

        # 2. PARTICIPANT DATA START DETECTION
        header_row = 0
        participants_found = False
        keywords = ['name', 'first join', 'last leave', 'duration', 'email', 'in-meeting duration']
        for i, row in df_raw.head(60).iterrows():
            row_vals_raw = [str(val).lower().strip() for val in row if pd.notna(val)]
            row_str = " ".join(row_vals_raw)
            if not participants_found:
                if '2. participants' in row_str or (len(row_vals_raw) == 1 and row_vals_raw[0] == 'participants'):
                    participants_found = True
                continue
            matches = sum(1 for val in row_vals_raw if any(key in val for key in keywords))
            if matches >= 3:
                header_row = i
                break
        
        if file_ext == 'csv':
            df = pd.read_csv(BytesIO(contents), skiprows=header_row)
        else:
            df = pd.read_excel(BytesIO(contents), skiprows=header_row)
        df.columns = [str(col).strip() for col in df.columns]

        # 3. CONSOLIDATE PARTICIPANTS (Group by Student)
        # We use a dict to merge rows: { student_id: {data} }
        consolidated_data = {} # student_id -> {joined, left, duration_sum, report_name}
        
        email_col = next((c for c in df.columns if 'email' in c.lower()), None)
        name_col = next((c for c in df.columns if 'name' in c.lower()), None)
        join_col = next((c for c in df.columns if 'join' in c.lower()), None)
        leave_col = next((c for c in df.columns if 'leave' in c.lower()), None)
        duration_col = next((c for c in df.columns if 'duration' in c.lower()), None)

        # Get all students enrolled in this course for matching and "Absent" logic
        enrolled_students = db.query(User).join(Enrollment, User.id == Enrollment.student_id).filter(
            Enrollment.cohort_id == cohort_id, Enrollment.course_id == course_id
        ).all()
        
        if not enrolled_students:
             enrolled_students = db.query(User).join(CohortSpecificEnrollment, User.id == CohortSpecificEnrollment.student_id).filter(
                CohortSpecificEnrollment.course_id == course_id
            ).all()
            
        # Fallback: Get all students in this cohort if no specific course enrollment found
        if not enrolled_students:
            from database import UserCohort
            enrolled_students = db.query(User).join(
                UserCohort, User.id == UserCohort.user_id
            ).filter(
                UserCohort.cohort_id == cohort_id,
                UserCohort.is_active == True
            ).all()
        
        student_id_map = {s.id: s for s in enrolled_students}
        success_count = 0
        failed_count = 0
        errors = []
        
        
        for index, row in df.iterrows():
            row_vals_raw = [str(val).strip() for val in row if pd.notna(val)]
            row_text = " ".join(row_vals_raw).lower().strip()
            if not row_text or (len(row_vals_raw) == 1 and 'activities' in row_text): break

            # Try to match student
            matched_student = None
            report_name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else "Unknown"
            report_name_clean = re.sub(r'\s*\([^)]*\)', '', report_name).strip()
            report_name_no_spaces = report_name_clean.replace(" ", "").lower()
            
            if email_col and pd.notna(row[email_col]):
                email = str(row[email_col]).strip().lower()
                matched_student = next((s for s in enrolled_students if s.email and s.email.lower() == email), None)
            
            # Tier 2: Exact Name Match
            if not matched_student and report_name_clean:
                matched_student = next((s for s in enrolled_students if 
                    (s.username.lower() == report_name_clean.lower()) or 
                    (s.username.lower() == report_name_no_spaces)
                ), None)

            # Tier 3: Smart Token Match (Fallback for variations like "Aditi H Nayak" vs "Aditi Nayak")
            if not matched_student and report_name_clean:
                report_tokens = set(report_name_clean.lower().split())
                for s in enrolled_students:
                    db_name = s.username.lower()
                    db_tokens = set(db_name.split())
                    
                    # Match if one set of tokens is a subset of the other
                    # This handles "Aditi Nayak" vs "Aditi H Nayak"
                    if report_tokens.issubset(db_tokens) or db_tokens.issubset(report_tokens):
                        # Verify significant overlap (at least 2 tokens or the only token)
                        common = report_tokens.intersection(db_tokens)
                        if len(common) >= 2 or (len(report_tokens) == 1 and len(common) == 1):
                            matched_student = s
                            break

            if not matched_student:
                failed_count += 1
                if len(errors) < 15: errors.append(f"Unmatched: {report_name}")
                continue

            # Parse times and duration
            try:
                u_join = pd.to_datetime(row[join_col]) if join_col and pd.notna(row[join_col]) else None
                u_leave = pd.to_datetime(row[leave_col]) if leave_col and pd.notna(row[leave_col]) else None
                u_dur = parse_duration_string(str(row[duration_col])) if duration_col and pd.notna(row[duration_col]) else 0.0
            except:
                u_join, u_leave, u_dur = None, None, 0.0

            # Merge into consolidation dict
            sid = matched_student.id
            if sid not in consolidated_data:
                consolidated_data[sid] = {
                    'first_join': u_join,
                    'last_leave': u_leave,
                    'total_duration': u_dur,
                    'report_name': report_name
                }
            else:
                if u_join and (not consolidated_data[sid]['first_join'] or u_join < consolidated_data[sid]['first_join']):
                    consolidated_data[sid]['first_join'] = u_join
                if u_leave and (not consolidated_data[sid]['last_leave'] or u_leave > consolidated_data[sid]['last_leave']):
                    consolidated_data[sid]['last_leave'] = u_leave
                consolidated_data[sid]['total_duration'] += u_dur

        # 4. FINAL MARKING & DATABASE UPDATE
        # Mark all enrolled students (including those not in report)
        use_smart_mode = start_time and end_time
        effective_min_duration = min_duration_minutes if min_duration_minutes is not None else 5
        
        for student in enrolled_students:
            sid = student.id
            report_info = consolidated_data.get(sid)
            
            if report_info:
                # Student found in report - check duration
                attended = report_info['total_duration'] >= effective_min_duration
                f_join = report_info['first_join']
                l_leave = report_info['last_leave']
                t_dur = report_info['total_duration']
                success_count += 1
            else:
                # Student NOT in report - mark ABSENT
                attended = False
                f_join, l_leave, t_dur = None, None, 0.0

            # Update DB
            attendance = db.query(CohortAttendance).filter(
                CohortAttendance.session_id == session_id,
                CohortAttendance.student_id == sid
            ).first()

            if attendance:
                attendance.attended = attended
                attendance.first_join_time = f_join
                attendance.last_leave_time = l_leave
                attendance.total_duration_minutes = t_dur
                attendance.updated_at = datetime.utcnow()
            else:
                attendance = CohortAttendance(
                    session_id=session_id,
                    student_id=sid,
                    attended=attended,
                    first_join_time=f_join,
                    last_leave_time=l_leave,
                    total_duration_minutes=t_dur
                )
                db.add(attendance)

        db.commit()
        
        # Calculate overall duration for response if possible
        overall_duration = None
        if start_time and end_time:
            try:
                s_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                e_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                overall_duration = (e_dt - s_dt).total_seconds() / 60
            except: pass

        return {
            "message": "Consolidated import completed",
            "success_count": success_count,
            "failed_count": failed_count, # Unmatched report rows
            "enrolled_count": len(enrolled_students),
            "errors": errors,
            "overall_duration_minutes": overall_duration,
            "summary_extracted": summary_data
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Consolidated Import Failed: {str(e)}")

