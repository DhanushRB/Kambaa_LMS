import re

class MockStudent:
    def __init__(self, id, username, email=None):
        self.id = id
        self.username = username
        self.email = email

def smart_match(report_name_clean, enrolled_students):
    report_name_no_spaces = report_name_clean.replace(" ", "").lower()
    
    # Tier 2: Exact Name Match
    matched = next((s for s in enrolled_students if 
        (s.username.lower() == report_name_clean.lower()) or 
        (s.username.lower() == report_name_no_spaces)
    ), None)
    
    if matched: return matched, "Tier 2"

    # Tier 3: Smart Token Match
    report_tokens = set(report_name_clean.lower().split())
    for s in enrolled_students:
        db_name = s.username.lower()
        db_tokens = set(db_name.split())
        
        if report_tokens.issubset(db_tokens) or db_tokens.issubset(report_tokens):
            common = report_tokens.intersection(db_tokens)
            if len(common) >= 2 or (len(report_tokens) == 1 and len(common) == 1):
                return s, "Tier 3"
                
    return None, "None"

# Test Data
db_students = [
    MockStudent(1, "Aditi H Nayak"),
    MockStudent(2, "Tejo Sridhar"),
    MockStudent(3, "Bala Tharun")
]

test_cases = [
    "Aditi Nayak",
    "Tejo",
    "Aditi H Nayak",
    "Bala Tharun (Guest)",
    "Unknown Student"
]

print(f"{'Report Name':<20} | {'Matched ID':<10} | {'Tier Used'}")
print("-" * 45)

for name in test_cases:
    clean_name = re.sub(r'\s*\([^)]*\)', '', name).strip()
    match, tier = smart_match(clean_name, db_students)
    match_id = match.id if match else "FAIL"
    print(f"{name:<20} | {match_id:<10} | {tier}")
