import pandas as pd

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"
df = pd.read_excel(filepath, header=None)

print(f"--- FIRST 20 ROWS SCAN ---")
for i, row in df.head(20).iterrows():
    row_vals = [str(val).lower().strip() for val in row if pd.notna(val)]
    row_str = " ".join(row_vals)
    print(f"Index {i:2d}: '{row_str}'")
