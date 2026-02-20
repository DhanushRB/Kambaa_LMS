import sys
import os

# Add backend directory to path
sys.path.append(os.getcwd())

from utils.user_utils import validate_email_zerobounce, normalize_email

def test_live_zerobounce(email_to_test):
    print(f"Testing ZeroBounce validation for: {email_to_test}...")
    
    # Test the validation logic
    res = validate_email_zerobounce(email_to_test)
    
    print("\n--- ZeroBounce Result ---")
    print(f"Status: {res.get('status')}")
    print(f"Sub-status: {res.get('sub_status')}")
    print(f"Is Valid (Deliverable): {res.get('valid')}")
    print(f"Message: {res.get('message')}")
    print("--------------------------\n")
    
    if res.get('status') == 'skipped':
        print("ALERT: Validation was SKIPPED. This usually means the API key in .env is not being read correctly.")
    elif res.get('status') == 'error':
        print(f"ALERT: An error occurred: {res.get('message')}")
    else:
        print("SUCCESS: ZeroBounce API is communicating correctly!")

if __name__ == "__main__":
    # You can change this email to any email you want to test
    test_email = "valid@example.com"
    if len(sys.argv) > 1:
        test_email = sys.argv[1]
        
    test_live_zerobounce(test_email)
