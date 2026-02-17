import os
import pandas as pd
from io import BytesIO
import re
import sys

# Add backend to path to import database models
sys.path.append(r"D:\LMS-v2\backend")
from database import SessionLocal, User
from sqlalchemy import func, or_

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"

def simulate_import():
    db = SessionLocal()
    try:
        with open(filepath, 'rb') as f:
            contents = f.read()
        
        df_raw = pd.read_excel(BytesIO(contents), header=None)
        
        # 1. Header Detection
        header_row = 0
        participants_found = False
        keywords = ['name', 'first join', 'last leave', 'duration', 'email', 'in-meeting duration']
        for i, row in df_raw.head(50).iterrows():
            row_vals_raw = [str(val).lower().strip() for val in row if pd.notna(val)]
            row_str = " ".join(row_vals_raw)
            if not participants_found:
                if '2. participants' in row_str:
                    participants_found = True
                continue
            matches = sum(1 for val in row_vals_raw if any(key in val for key in keywords))
            if matches >= 3:
                header_row = i
                break
        
        print(f"Header row: {header_row}")
        df = pd.read_excel(BytesIO(contents), skiprows=header_row)
        df.columns = [str(col).strip() for col in df.columns]
        
        name_col = next((c for c in df.columns if 'name' in c.lower()), None)
        processed_count = 0
        
        for index, row in df.iterrows():
            row_vals_raw = [str(val).lower().strip() for val in row if pd.notna(val)]
            row_text = " ".join(row_vals_raw).strip()
            if not row_text: continue
            
            # THE VERY STRICT STOP CONDITION
            # Only stop if it's strictly a header (1 column) or specifically the 3rd section header with no data
            if 'activities' in row_text and (len(row_vals_raw) == 1):
                print(f"BREAK triggered at index {index}, row_text: '{row_text}'")
                break
            
            processed_count += 1
            if processed_count % 50 == 0:
                print(f"Processed {processed_count} rows...")

        print(f"SUMMARY: Total participants found={processed_count}")
        print(f"Last processed index in df: {index}")
    finally:
        db.close()

simulate_import()
