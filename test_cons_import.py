import os
import pandas as pd
from io import BytesIO
import re
import sys
from datetime import datetime

# Add backend to path to import database models
sys.path.append(r"D:\LMS-v2\backend")
from database import SessionLocal, User, Enrollment
from cohort_specific_models import CohortAttendance, CohortCourseSession, CohortSpecificEnrollment

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"

def parse_duration_string(dur_str: str) -> float:
    if not dur_str or not isinstance(dur_str, str):
        return 0.0
    dur_str = dur_str.lower().strip()
    total_minutes = 0.0
    h_match = re.search(r'(\d+)\s*h', dur_str)
    if h_match: total_minutes += int(h_match.group(1)) * 60
    m_match = re.search(r'(\d+)\s*m', dur_str)
    if m_match: total_minutes += int(m_match.group(1))
    s_match = re.search(r'(\d+)\s*s', dur_str)
    if s_match: total_minutes += int(s_match.group(1)) / 60
    
    if total_minutes > 0: return total_minutes
    if ':' in dur_str:
        parts = dur_str.split(':')
        try:
            if len(parts) == 3: return int(parts[0])*60 + int(parts[1]) + int(parts[2])/60
            elif len(parts) == 2: return int(parts[0]) + int(parts[1])/60
        except: pass
    return 0.0

def simulate_consolidated_import():
    db = SessionLocal()
    try:
        with open(filepath, 'rb') as f:
            contents = f.read()
        
        df_raw = pd.read_excel(BytesIO(contents), header=None)
        
        # 1. SUMMARY
        summary_data = {}
        for i, row in df_raw.head(15).iterrows():
            row_vals = [str(val).strip() for val in row if pd.notna(val)]
            row_str = " ".join(row_vals).lower()
            if 'meeting title' in row_str and len(row_vals) >= 2: summary_data['title'] = row_vals[1]
            elif 'start time' in row_str and len(row_vals) >= 2: summary_data['start_time'] = row_vals[1]
            elif 'overall meeting duration' in row_str and len(row_vals) >= 2: summary_data['duration_min'] = parse_duration_string(row_vals[1])

        print(f"EXTRACTED SUMMARY: {summary_data}")

        # 2. HEADER
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
        
        print(f"DATA HEADER AT: {header_row}")
        df = pd.read_excel(BytesIO(contents), skiprows=header_row)
        df.columns = [str(col).strip() for col in df.columns]

        # 3. MERGING LOGIC TEST
        consolidated = {}
        name_col = next(c for c in df.columns if 'name' in c.lower())
        join_col = next(c for c in df.columns if 'join' in c.lower())
        dur_col = next(c for c in df.columns if 'duration' in c.lower())
        
        # We'll just print merges for demonstration in sim
        for index, row in df.iterrows():
            row_vals = [str(val).strip() for val in row if pd.notna(val)]
            if not row_vals or (len(row_vals) == 1 and 'activities' in " ".join(row_vals).lower()): break
            
            name = str(row[name_col]).strip()
            u_join = pd.to_datetime(row[join_col]) if pd.notna(row[join_col]) else None
            u_dur = parse_duration_string(str(row[dur_col])) if pd.notna(row[dur_col]) else 0.0
            
            if name not in consolidated:
                consolidated[name] = {'count': 1, 'first_join': u_join, 'total_dur': u_dur}
            else:
                consolidated[name]['count'] += 1
                consolidated[name]['total_dur'] += u_dur
                if u_join and (not consolidated[name]['first_join'] or u_join < consolidated[name]['first_join']):
                    consolidated[name]['first_join'] = u_join

        merges = {k: v for k, v in consolidated.items() if v['count'] > 1}
        print(f"Consolidated into {len(consolidated)} unique names.")
        print(f"Found {len(merges)} merged duplicate records.")
        for name, data in list(merges.items())[:5]:
            print(f"  - {name}: {data['count']} entries, total {data['total_dur']:.1f} min")

    finally:
        db.close()

simulate_consolidated_import()
