
import asyncio
import sys
import os
import logging

# Ensure backend directory is in path
sys.path.append(os.path.abspath("d:/LMS-v2/backend"))

from database import SessionLocal
from email_utils import send_content_added_notification

# Configure logging to see our debug messages
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_debug():
    print("--- Running REAL send_content_added_notification for Session 346 ---")
    db = SessionLocal()
    try:
        await send_content_added_notification(
            db=db,
            session_id=346,
            content_title="Debug Resource",
            content_type="RESOURCE",
            session_type="cohort",
            description="Testing real notification flow"
        )
    except Exception as e:
        print(f"FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_debug())
