
import sys
import os

# Add the current directory to sys.path
sys.path.append(os.getcwd())

try:
    from main import app
    print("Listing all registered routes:")
    for route in app.routes:
        path = getattr(route, "path", "No Path")
        name = getattr(route, "name", "No Name")
        methods = getattr(route, "methods", "N/A")
        print(f"Path: {path}, Name: {name}, Methods: {methods}")
        if hasattr(route, "routes"): # For Mount objects
            print(f"  [Sub-routes for {path}]")
            for sub_route in route.routes:
                sub_path = getattr(sub_route, "path", "No Path")
                sub_methods = getattr(sub_route, "methods", "N/A")
                print(f"    Sub-Path: {sub_path}, Methods: {sub_methods}")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Error: {e}")
