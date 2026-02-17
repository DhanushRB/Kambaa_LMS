import pandas as pd
from io import BytesIO

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"

with open(filepath, 'rb') as f:
    contents = f.read()

# Read raw
df_raw = pd.read_excel(BytesIO(contents), header=None)

print("=== ROWS 0-10 (RAW DATA) ===\n")
for i in range(11):
    row = df_raw.iloc[i]
    print(f"Row {i}:")
    print(f"  [0] = {repr(row[0])} (type: {type(row[0]).__name__})")
    print(f"  [1] = {repr(row[1])} (type: {type(row[1]).__name__})")
    if pd.notna(row[1]):
        print(f"  [1] as string = '{row[1]}'")
        if hasattr(row[1], 'isoformat'):
            print(f"  [1] as datetime = {row[1]}")
    print()
