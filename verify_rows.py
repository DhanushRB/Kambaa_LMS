import pandas as pd

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"
df_raw = pd.read_excel(filepath, sheet_name=0, header=None)

print("=== CHECKING ROWS 3-5 (0-indexed) ===\n")
for i in [3, 4, 5]:
    col_a = str(df_raw.iloc[i, 0]) if pd.notna(df_raw.iloc[i, 0]) else "NaN"
    col_b = str(df_raw.iloc[i, 1]) if pd.notna(df_raw.iloc[i, 1]) else "NaN"
    print(f"Row {i} (Excel row {i+1}):")
    print(f"  A{i+1} (Column 0): '{col_a}'")
    print(f"  B{i+1} (Column 1): '{col_b}'")
    print()
