import pandas as pd
from datetime import datetime

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"
df_raw = pd.read_excel(filepath, sheet_name=0, header=None)

print("=== EXTRACTING SESSION TIMES FROM SUMMARY ===\n")

# Find Start time and End time in first column
start_time_str = None
end_time_str = None

for i in range(10):
    label = str(df_raw.iloc[i, 0]).strip() if pd.notna(df_raw.iloc[i, 0]) else ""
    value = df_raw.iloc[i, 1] if len(df_raw.columns) > 1 and pd.notna(df_raw.iloc[i, 1]) else None
    
    if 'start' in label.lower() and 'time' in label.lower():
        start_time_str = str(value)
        print(f"Row {i}: '{label}' = '{value}'")
        print(f"  Type: {type(value).__name__}")
        print(f"  String: '{start_time_str}'")
        
    elif 'end' in label.lower() and 'time' in label.lower():
        end_time_str = str(value)
        print(f"Row {i}: '{label}' = '{value}'")
        print(f"  Type: {type(value).__name__}")
        print(f"  String: '{end_time_str}'")

print(f"\n=== PARSING TIMES ===\n")
print(f"Start time string: '{start_time_str}'")
print(f"End time string: '{end_time_str}'")

# Parse the times
import re
def parse_time_string(time_str):
    # Format: "2/15/26, 6:12:54 PM"
    match = re.match(r'(\d{1,2})/(\d{1,2})/(\d{2,4}),?\s+(\d{1,2}):(\d{2}):(\d{2})\s*(AM|PM)', time_str, re.I)
    if match:
        month, day, year, hour, minute, second, ampm = match.groups()
        year = int(year)
        if year < 100:
            year += 2000
        hour = int(hour)
        if ampm.upper() == 'PM' and hour != 12:
            hour += 12
        elif ampm.upper() == 'AM' and hour == 12:
            hour = 0
        
        dt = datetime(year, int(month), int(day), hour, int(minute), int(second))
        return dt
    return None

if start_time_str and end_time_str:
    start_dt = parse_time_string(start_time_str)
    end_dt = parse_time_string(end_time_str)
    
    if start_dt and end_dt:
        print(f"\nParsed Start: {start_dt}")
        print(f"Parsed End: {end_dt}")
        duration = (end_dt - start_dt).total_seconds() / 60
        print(f"Duration: {duration:.0f} minutes")
        print(f"\nISO Format:")
        print(f"  Start: {start_dt.isoformat()}")
        print(f"  End: {end_dt.isoformat()}")
