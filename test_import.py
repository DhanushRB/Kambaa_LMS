
import sys
import os

# Add the current directory to sys.path
sys.path.append(os.getcwd())

try:
    print("Attempting to import calendar_events_api...")
    import calendar_events_api
    print("Import successful!")
    print(f"Router object: {calendar_events_api.router}")
    print("Routes in router:")
    for route in calendar_events_api.router.routes:
        print(f"  Path: {route.path}, Methods: {route.methods}")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Import failed: {e}")
