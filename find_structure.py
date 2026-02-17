import pandas as pd

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"

# Read Excel file and check all sheets
xl_file = pd.ExcelFile(filepath)
print(f"Sheets in file: {xl_file.sheet_names}\n")

# Read first sheet without any processing
df = pd.read_excel(filepath, sheet_name=0, header=None)

print("=== ROWS 0-20 (showing first 8 columns) ===\n")
for i in range(min(21, len(df))):
    row_data = []
    for j in range(min(8, len(df.columns))):
        val = df.iloc[i, j]
        if pd.notna(val):
            row_data.append(f"[{j}]='{val}'")
    print(f"Row {i:2d}: {' | '.join(row_data)}")

# Try to find where actual data starts
print("\n=== LOOKING FOR DATA PATTERN ===")
for i in range(min(25, len(df))):
    # Count non-null values in row
    non_null = df.iloc[i].notna().sum()
    if non_null > 5:  # Likely a data row
        print(f"Row {i} has {non_null} non-null values")
        if i < 15:
            print(f"  Sample: {[str(df.iloc[i, j])[:30] for j in range(min(6, len(df.columns)))]}")
