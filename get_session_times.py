import pandas as pd
from datetime import datetime
import re

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"

# Read with header at row 9
df = pd.read_excel(filepath, sheet_name=0, skiprows=9)
df.columns = [str(col).strip() for col in df.columns]

print("=== COLUMN NAMES ===")
for i, col in enumerate(df.columns):
    print(f"{i}: {col}")

print(f"\n=== FIRST 3 PARTICIPANT ROWS ===")
for idx in range(min(3, len(df))):
    print(f"\nParticipant {idx+1}:")
    for col in ['Name', 'First Join', 'Last Leave', 'Email', 'Role']:
        if col in df.columns:
            print(f"  {col}: {df[col].iloc[idx]}")

# Find join/leave columns
join_cols = [col for col in df.columns if 'join' in col.lower()]
leave_cols = [col for col in df.columns if 'leave' in col.lower()]

print(f"\n=== TIME COLUMNS ===")
print(f"Join columns: {join_cols}")
print(f"Leave columns: {leave_cols}")

if join_cols and leave_cols:
    print(f"\n=== EXTRACTING SESSION TIME RANGE ===")
    join_col = join_cols[0]
    leave_col = leave_cols[0]
    
    join_times = []
    leave_times = []
    
    for idx in range(len(df)):
        join_val = df[join_col].iloc[idx]
        leave_val = df[leave_col].iloc[idx]
        
        if pd.notna(join_val):
            try:
                jt = pd.to_datetime(join_val)
                join_times.append(jt)
            except:
                pass
        
        if pd.notna(leave_val):
            try:
                lt = pd.to_datetime(leave_val)
                leave_times.append(lt)
            except:
                pass
    
    if join_times and leave_times:
        earliest_join = min(join_times)
        latest_leave = max(leave_times)
        duration = (latest_leave - earliest_join).total_seconds() / 60
        
        print(f"Earliest join: {earliest_join}")
        print(f"Latest leave: {latest_leave}")
        print(f"Duration: {duration:.0f} minutes")
