import pandas as pd

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"
df = pd.read_excel(filepath, sheet_name=0, header=None)

print("=== KEY ROWS ===\n")
for row_num in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
    print(f"\nRow {row_num}:")
    for col in range(min(10, len(df.columns))):
        val = df.iloc[row_num, col]
        if pd.notna(val):
            print(f"  Col{col}: {val}")

# Try reading with row 9 as header
print("\n\n=== TRYING ROW 9 AS HEADER ===\n")
df_data = pd.read_excel(filepath, sheet_name=0, skiprows=9)
df_data.columns = [str(col).strip() for col in df_data.columns]

print("Columns:")
for i, col in enumerate(df_data.columns[:10]):
    print(f"  {i}: {col}")

print(f"\nFirst row data:")
if len(df_data) > 0:
    for col in df_data.columns[:8]:
        print(f"  {col}: {df_data[col].iloc[0]}")
