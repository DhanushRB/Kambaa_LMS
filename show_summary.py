import pandas as pd

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"
df_raw = pd.read_excel(filepath, sheet_name=0, header=None)

print("=== ALL SUMMARY ROWS (0-10) ===\n")
for i in range(11):
    col0 = str(df_raw.iloc[i, 0]) if pd.notna(df_raw.iloc[i, 0]) else "NaN"
    col1 = str(df_raw.iloc[i, 1]) if pd.notna(df_raw.iloc[i, 1]) else "NaN"
    print(f"Row {i}: '{col0}' = '{col1}'")
