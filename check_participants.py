import pandas as pd

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"
df_raw = pd.read_excel(filepath, sheet_name=0, header=None)

print("=== CHECKING ROWS 8-15 ===\n")
for i in range(8, 16):
    row_vals = []
    for j in range(min(10, len(df_raw.columns))):
        val = df_raw.iloc[i, j]
        row_vals.append(f"[{j}]='{val}'")
    print(f"Row {i:2d}: {' | '.join(row_vals)}")

print("\n=== ROWS 45-55 ===\n")
for i in range(45, 56):
    row_vals = []
    for j in range(min(10, len(df_raw.columns))):
        val = df_raw.iloc[i, j]
        row_vals.append(f"[{j}]='{val}'")
    print(f"Index {i:2d}: {' | '.join(row_vals)}")
