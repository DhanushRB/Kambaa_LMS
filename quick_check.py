import pandas as pd
from io import BytesIO

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"

with open(filepath, 'rb') as f:
    contents = f.read()

df_raw = pd.read_excel(BytesIO(contents), header=None)

print("SUMMARY SECTION:")
for i in range(7):
    print(f"Row {i}: [{df_raw.iloc[i, 0]}] = [{df_raw.iloc[i, 1]}]")

# Read with header
df = pd.read_excel(BytesIO(contents), skiprows=6)
df.columns = [str(col).strip() for col in df.columns]

print("\nCOLUMNS:")
for i, col in enumerate(df.columns):
    print(f"{i}. {col}")

print("\nFIRST ROW DATA:")
for col in df.columns:
    val = df[col].iloc[0] if len(df) > 0 else 'N/A'
    print(f"{col}: {val}")
