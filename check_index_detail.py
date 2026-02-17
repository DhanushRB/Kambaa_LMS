import pandas as pd

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"
df = pd.read_excel(filepath, header=None)

def dump_row(idx):
    print(f"\n--- DETAIL FOR INDEX {idx} ---")
    row = df.iloc[idx]
    for j, val in enumerate(row):
        if pd.notna(val) and str(val).strip():
            print(f"Col {j}: '{val}'")

dump_row(51)
dump_row(215)
