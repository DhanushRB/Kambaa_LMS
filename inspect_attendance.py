import pandas as pd
from io import BytesIO

# Read the file
filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"

with open(filepath, 'rb') as f:
    contents = f.read()

# Read without headers first to scan for them
df_raw = pd.read_excel(BytesIO(contents), header=None)

# Dynamic Header Detection (same as backend)
header_row = 0
keywords = ['name', 'email', 'join', 'leave', 'student', 'attendance', 'time', 'duration']
for i, row in df_raw.head(20).iterrows():
    row_vals = [str(val).lower() for val in row if pd.notna(val)]
    # If any of our keywords are in the typical header positions
    if any(any(key in str(val) for key in keywords) for val in row_vals):
        # Check if it looks like a real header (not just summary text)
        if len([v for v in row_vals if v.strip()]) >= 2:
            print(f"Found header at row {i}: {row_vals}")
            header_row = i
            break

# Re-read with detected header row
df = pd.read_excel(BytesIO(contents), skiprows=header_row)

# Canonicalize column names
df.columns = [str(col).strip() for col in df.columns]

print(f"\nHeader row: {header_row}")
print(f"\nColumns after processing:")
for i, col in enumerate(df.columns):
    print(f"  {i}: {col}")

print(f"\n=== FIRST 5 DATA ROWS ===")
print(df.head(5))

# Find time-related columns
print(f"\n=== TIME-RELATED COLUMNS ===")
for col in df.columns:
    col_lower = col.lower()
    if any(keyword in col_lower for keyword in ['join', 'leave', 'time', 'duration', 'start', 'end']):
        print(f"\n{col}:")
        print(f"  Sample values: {df[col].head(3).tolist()}")
        print(f"  Data type: {df[col].dtype}")
