import pandas as pd
import sys

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"
df = pd.read_excel(filepath, header=None)

print(f"Total rows in file: {len(df)}")
for i, row in df.iterrows():
    row_vals = [str(val).lower().strip() for val in row if pd.notna(val)]
    row_str = " ".join(row_vals)
    
    # Print if it looks like a section header
    if 'participants' in row_str or 'activities' in row_str:
        if len(row_vals) <= 3: # Section headers usually have only the title
            print(f"Index {i:4d}: SECTION? '{row_str}' (Row vals count: {len(row_vals)})")
        else:
            # Just to be sure, print if it's the keywords
            if 'participants' in row_str or 'activities' in row_str:
                 print(f"Index {i:4d}: DATA? '{row_str[:50]}...' (Row vals count: {len(row_vals)})")
