import logging
import sys
import traceback

# Set logging level to see if any routers fail to load
logging.basicConfig(level=logging.INFO)

from main import app

print("\n--- CHECKING cohort_session_content_api ---")
try:
    from cohort_session_content_api import router
    print(f"cohort_session_content_api router prefix: {router.prefix}")
except Exception:
    print("Error importing cohort_session_content_api:")
    traceback.print_exc()

print("\n--- ALL REGISTERED ROUTES ---")
for route in app.router.routes:
    path = getattr(route, "path", None)
    methods = getattr(route, "methods", None)
    if path:
        print(f"Path: {path}, Methods: {methods}")
