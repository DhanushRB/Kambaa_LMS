import pandas as pd
from io import BytesIO
import re

filepath = r"D:\LMS-v2\frontend\Kambaa's AI Career Launchpad - Session 7 - Attendance report 2-15-26.xlsx"

def parse_duration_string(dur_str: str) -> float:
    if not dur_str or not isinstance(dur_str, str):
        if isinstance(dur_str, (int, float)):
            return float(dur_str)
        return 0.0
    dur_str = dur_str.lower().strip()
    if any(unit in dur_str for unit in ['h', 'm', 's']):
        total_minutes = 0.0
        h_match = re.search(r'(\d+)\s*h', dur_str)
        if h_match: total_minutes += int(h_match.group(1)) * 60
        m_match = re.search(r'(\d+)\s*m', dur_str)
        if m_match: total_minutes += int(m_match.group(1))
        s_match = re.search(r'(\d+)\s*s', dur_str)
        if s_match: total_minutes += int(s_match.group(1)) / 60
        if total_minutes > 0: return total_minutes
    if ':' in dur_str:
        parts = dur_str.split(':')
        try:
            if len(parts) == 3: return int(parts[0])*60 + int(parts[1]) + int(parts[2])/60
            elif len(parts) == 2: return int(parts[0]) + int(parts[1])/60
        except ValueError: pass
    try:
        clean_val = re.sub(r'[^\d.]', '', dur_str)
        if clean_val: return float(clean_val)
    except ValueError: pass
    return 0.0

print("--- DIAGNOSTIC START ---")
df_raw = pd.read_excel(filepath, header=None)

print("\n=== FIRST 15 ROWS ===\n")
for i, row in df_raw.head(15).iterrows():
    vals = [f"[{j}]='{val}'" for j, val in enumerate(row) if pd.notna(val)]
    print(f"Index {i:2d}: {' | '.join(vals)}")

# Header Detection Logic copied from backend
header_row = 0
participants_section_found = False
keywords = ['name', 'first join', 'last leave', 'duration', 'email']

print("\nScanning for headers...")
for i, row in df_raw.head(50).iterrows():
    # Join all non-null values in the row to check for section markers
    row_vals_raw = [str(val).lower().strip() for val in row if pd.notna(val)]
    row_str = " ".join(row_vals_raw)
    
    # Step 1: Look for section header (Specifically "2. Participants")
    if not participants_section_found:
        if '2. participants' in row_str or (len(row_vals_raw) == 1 and row_vals_raw[0] == 'participants'):
            participants_section_found = True
            print(f"Found 'Participants' section at index {i}")
        continue
    
    # Step 2: Look for actual data columns (Require at least 3 matches)
    matches = 0
    for val in row_vals_raw:
        if any(key in val for key in keywords):
            matches += 1
    
    if matches >= 3:
        header_row = i
        print(f"Found data header at index {i} with {matches} matches: {row_vals_raw}")
        break

if not participants_section_found:
    print("CRITICAL: 'Participants' section not found!")
if header_row == 0 and not participants_section_found:
    print("CRITICAL: Data header not found!")

print(f"\nRe-reading with skiprows={header_row}...")
df = pd.read_excel(filepath, skiprows=header_row)
df.columns = [str(col).strip() for col in df.columns]
print(f"Columns: {df.columns.tolist()}")

processed_count = 0
consecutive_empty_rows = 0
print("\nIterating rows with gap skipping (limit 50 empty)...")
for index, row in df.iterrows():
    row_vals_raw = [str(val).lower().strip() for val in row if pd.notna(val)]
    row_text = " ".join(row_vals_raw).strip()
    
    if not row_text:
        consecutive_empty_rows += 1
        if consecutive_empty_rows > 50:
            print(f"Index {index}: Reached limit of 50 empty rows - BREAKING")
            break
        continue
    
    consecutive_empty_rows = 0
    if 'in-meeting activities' in row_text:
        print(f"Index {index}: 'In-Meeting Activities' detected - BREAKING")
        break
    
    processed_count += 1
    if processed_count % 50 == 0 or processed_count <= 5:
        print(f"Processed: {processed_count} (Current Index: {index}, Name: '{row.iloc[0]}')")

print(f"\nFinal count of rows with content: {processed_count}")
print("--- DIAGNOSTIC END ---")
