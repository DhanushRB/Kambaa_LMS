import requests
import json

def verify_fix():
    # Since we need a token, and I don't have one easily, 
    # I'll just check if the code changes are correctly returning strings with 'Z'
    # I can mock a DB session and call the function directly if I want to be thorough.
    
    from routers.admin_router import get_all_system_logs
    from database import SessionLocal
    import asyncio
    
    async def run_check():
        db = SessionLocal()
        try:
            # We don't need real admin user for the logic check if we bypass the Depends
            # But get_all_system_logs expects a DB session
            response = await get_all_system_logs(page=1, limit=5, db=db, current_admin=None)
            logs = response.get("data", {}).get("logs", [])
            for log in logs:
                ts = log.get("timestamp")
                print(f"Log ID: {log.get('id')}, Timestamp: {ts}")
                if ts and not ts.endswith('Z'):
                    print(f"FAILED: Timestamp {ts} does not end with 'Z'")
                elif ts:
                    print(f"PASSED: Timestamp {ts} ends with 'Z'")
        finally:
            db.close()

    asyncio.run(run_check())

if __name__ == "__main__":
    verify_fix()
