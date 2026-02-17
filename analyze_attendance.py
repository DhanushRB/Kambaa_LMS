import pandas as pd
from io import BytesIO

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"

with open(filepath, 'rb') as f:
    contents = f.read()

df_raw = pd.read_excel(BytesIO(contents), header=None)

print("=== SUMMARY SECTION (Rows 0-10) ===\n")
for i in range(min(11, len(df_raw))):
    print(f"Row {i}: Col0='{df_raw.iloc[i, 0]}' | Col1='{df_raw.iloc[i, 1]}'")

# Read with header at row 6
df = pd.read_excel(BytesIO(contents), skiprows=6)
df.columns = [str(col).strip() for col in df.columns]

print(f"\n=== COLUMN NAMES (after row 6) ===")
for i, col in enumerate(df.columns):
    print(f"{i}: {col}")

print(f"\n=== FIRST 3 DATA ROWS ===")
for idx in range(min(3, len(df))):
    print(f"\nRow {idx}:")
    for col in df.columns[:8]:  # First 8 columns
        print(f"  {col}: {df[col].iloc[idx]}")
