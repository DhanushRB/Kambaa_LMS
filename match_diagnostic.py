import sys
import os
import pandas as pd
from io import BytesIO
import re

# Add backend to path
sys.path.append(r"D:\LMS-v2\backend")

from database import SessionLocal, User, Enrollment
from cohort_specific_models import CohortSpecificEnrollment

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"

def diagnostic_match():
    db = SessionLocal()
    try:
        # 1. Check Enrolled Students
        cohort_id = 16
        course_id = 15
        
        enrolled_students = db.query(User).join(Enrollment, User.id == Enrollment.student_id).filter(
            Enrollment.cohort_id == cohort_id, Enrollment.course_id == course_id
        ).all()
        if not enrolled_students:
             enrolled_students = db.query(User).join(CohortSpecificEnrollment, User.id == CohortSpecificEnrollment.student_id).filter(
                CohortSpecificEnrollment.course_id == course_id
            ).all()
        
        print(f"DIAGNOSTIC: Enrolled students found in DB: {len(enrolled_students)}")
        for s in enrolled_students[:5]:
            print(f"  - DB Student: ID={s.id}, Username='{s.username}', Email='{s.email}'")

        if not os.path.exists(filepath):
            print(f"ERROR: File not found at {filepath}")
            return

        with open(filepath, 'rb') as f:
            contents = f.read()
        
        df_raw = pd.read_excel(BytesIO(contents), header=None)
        
        # Detect header
        header_row = 0
        participants_found = False
        keywords = ['name', 'first join', 'last leave', 'duration', 'email']
        for i, row in df_raw.head(60).iterrows():
            row_vals_raw = [str(val).lower().strip() for val in row if pd.notna(val)]
            if not participants_found:
                if '2. participants' in " ".join(row_vals_raw): participants_found = True
                continue
            if sum(1 for val in row_vals_raw if any(key in val for key in keywords)) >= 3:
                header_row = i
                break
        
        df = pd.read_excel(BytesIO(contents), skiprows=header_row)
        df.columns = [str(col).strip() for col in df.columns]
        
        name_col = next((c for c in df.columns if 'name' in c.lower()), None)
        email_col = next((c for c in df.columns if 'email' in c.lower()), None)
        
        print(f"DIAGNOSTIC: Columns detected: {df.columns.tolist()}")
        print(f"DIAGNOSTIC: Name Col='{name_col}', Email Col='{email_col}'")

        success = 0
        failed = 0
        unique_failed_names = set()

        for index, row in df.iterrows():
            row_vals = [str(val).strip() for val in row if pd.notna(val)]
            if not row_vals or (len(row_vals) == 1 and 'activities' in " ".join(row_vals).lower()): break
            
            report_name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else ""
            report_name_clean = re.sub(r'\s*\([^)]*\)', '', report_name).strip()
            report_name_no_spaces = report_name_clean.replace(" ", "").lower()
            
            matched = False
            # Try matching logic
            if email_col and pd.notna(row[email_col]):
                email = str(row[email_col]).strip().lower()
                if any(s.email and s.email.lower() == email for s in enrolled_students):
                    matched = True
            
            if not matched and report_name_clean:
                if any((s.username.lower() == report_name_clean.lower()) or 
                       (s.username.lower() == report_name_no_spaces) or
                       (report_name_clean.lower() in s.username.lower()) or
                       (s.username.lower() in report_name_clean.lower()) 
                       for s in enrolled_students):
                    matched = True
            
            if matched:
                success += 1
            else:
                failed += 1
                unique_failed_names.add(report_name_clean)

        print(f"DIAGNOSTIC SUMMARY: Success={success}, Failed={failed}")
        print(f"UNIQUE FAILED NAMES (Sample 10): {list(unique_failed_names)[:10]}")

    finally:
        db.close()

if __name__ == "__main__":
    diagnostic_match()
