import pandas as pd
from io import BytesIO
import re

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"

def parse_duration_string(dur_str: str) -> float:
    if not dur_str or not isinstance(dur_str, str): return 0.0
    dur_str = dur_str.lower().strip()
    if any(unit in dur_str for unit in ['h', 'm', 's']):
        total_m = 0.0
        h = re.search(r'(\d+)\s*h', dur_str)
        if h: total_m += int(h.group(1)) * 60
        m = re.search(r'(\d+)\s*m', dur_str)
        if m: total_m += int(m.group(1))
        s = re.search(r'(\d+)\s*s', dur_str)
        if s: total_m += int(s.group(1)) / 60
        return total_m
    if ':' in dur_str:
        parts = dur_str.split(':')
        if len(parts) == 3: return int(parts[0])*60 + int(parts[1]) + int(parts[2])/60
        elif len(parts) == 2: return int(parts[0]) + int(parts[1])/60
    return 0.0

print("--- FULL BACKEND SIMULATION ---")
with open(filepath, 'rb') as f:
    contents = f.read()

df_raw = pd.read_excel(BytesIO(contents), header=None)

# 1. Header Detection
header_row = 0
participants_found = False
keywords = ['name', 'first join', 'last leave', 'duration', 'email']

for i, row in df_raw.head(50).iterrows():
    row_vals_raw = [str(val).lower().strip() for val in row if pd.notna(val)]
    row_str = " ".join(row_vals_raw)
    
    if not participants_found:
        if '2. participants' in row_str or (len(row_vals_raw) == 1 and row_vals_raw[0] == 'participants'):
            participants_found = True
            print(f"DEBUG: Found 'Participants' section at index {i}")
        continue
    
    matches = sum(1 for val in row_vals_raw if any(key in val for key in keywords))
    if matches >= 3:
        header_row = i
        print(f"DEBUG: Found data header at index {i} with {matches} matches: {row_vals_raw}")
        break

if header_row == 0:
    print("ERROR: Header detection failed!")
    exit(1)

# 2. Re-read
df = pd.read_excel(BytesIO(contents), skiprows=header_row)
df.columns = [str(col).strip() for col in df.columns]
print(f"DEBUG: Columns detected: {df.columns.tolist()}")

# 3. Iterate
success_count = 0
failed_count = 0
consecutive_empty = 0
processed_indices = []

for index, row in df.iterrows():
    row_vals_raw = [str(val).lower().strip() for val in row if pd.notna(val)]
    row_text = " ".join(row_vals_raw).strip()
    
    if not row_text:
        consecutive_empty += 1
        if consecutive_empty > 50: 
            print(f"DEBUG: Row {index} is empty (consecutive={consecutive_empty}) - BREAKING")
            break
        continue
    
    consecutive_empty = 0
    if 'in-meeting activities' in row_text:
        print(f"DEBUG: STOP TRIGGERED at Row {index} (Spreadsheet row {index + header_row + 2})")
        print(f"DEBUG: Row Text: '{row_text}'")
        print(f"DEBUG: Row Vals: {row_vals_raw}")
        break
    
    # Simulate student matching (just counting for now)
    processed_indices.append(index)
    failed_count += 1 # Every row "fails" simulation because we don't check DB here
    
    if len(processed_indices) <= 5 or len(processed_indices) > 200:
        print(f"DEBUG: Processed Row {index}: '{row.iloc[0]}'")

print(f"\n--- RESULTS ---")
print(f"Total rows in df: {len(df)}")
print(f"Total rows actually processed: {len(processed_indices)}")
print(f"Success/Failed simulated: 0/{failed_count}")
print("--- END ---")
