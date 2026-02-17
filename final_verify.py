import sys
import os
import pandas as pd
from io import BytesIO
import re

# Add backend to path
sys.path.append(r"D:\LMS-v2\backend")

from database import SessionLocal, User, Enrollment, UserCohort
from cohort_specific_models import CohortSpecificEnrollment

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"

def final_diagnostic():
    db = SessionLocal()
    try:
        cohort_id = 16
        course_id = 15
        
        # Mimic new logic
        enrolled_students = db.query(User).join(Enrollment, User.id == Enrollment.student_id).filter(
            Enrollment.cohort_id == cohort_id, Enrollment.course_id == course_id
        ).all()
        if not enrolled_students:
             enrolled_students = db.query(User).join(CohortSpecificEnrollment, User.id == CohortSpecificEnrollment.student_id).filter(
                CohortSpecificEnrollment.course_id == course_id
            ).all()
        if not enrolled_students:
            enrolled_students = db.query(User).join(
                UserCohort, User.id == UserCohort.user_id
            ).filter(
                UserCohort.cohort_id == cohort_id,
                UserCohort.is_active == True
            ).all()
        
        print(f"DIAGNOSTIC: Students found with new logic: {len(enrolled_students)}")

        if not os.path.exists(filepath):
            print(f"ERROR: File not found")
            return

        with open(filepath, 'rb') as f:
            contents = f.read()
        
        df_raw = pd.read_excel(BytesIO(contents), header=None)
        
        # Detect header row 9
        df = pd.read_excel(BytesIO(contents), skiprows=9)
        df.columns = [str(col).strip() for col in df.columns]
        
        name_col = next((c for c in df.columns if 'name' in c.lower()), None)
        
        success = 0
        failed = 0
        for index, row in df.iterrows():
            row_vals = [str(val).strip() for val in row if pd.notna(val)]
            if not row_vals or (len(row_vals) == 1 and 'activities' in " ".join(row_vals).lower()): break
            
            report_name = str(row[name_col]).strip()
            report_name_clean = re.sub(r'\s*\([^)]*\)', '', report_name).strip()
            report_name_no_spaces = report_name_clean.replace(" ", "").lower()
            
            matched = False
            if report_name_clean:
                if any((s.username.lower() == report_name_clean.lower()) or 
                       (s.username.lower() == report_name_no_spaces) or
                       (report_name_clean.lower() in s.username.lower()) or
                       (s.username.lower() in report_name_clean.lower()) 
                       for s in enrolled_students):
                    matched = True
            
            if matched: success += 1
            else: failed += 1

        print(f"DIAGNOSTIC SUMMARY: Success={success}, Failed={failed}")

    finally:
        db.close()

if __name__ == "__main__":
    final_diagnostic()
