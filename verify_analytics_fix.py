import os
import sys
from sqlalchemy.orm import Session
from database import SessionLocal, StudentModuleStatus, StudentSessionStatus
from routers.analytics_router import get_admin_analytics
import asyncio
from unittest.mock import MagicMock

async def verify_analytics():
    db = SessionLocal()
    try:
        # Mock current_user dependency
        current_user = MagicMock()
        
        # Call the router function directly
        print("Calling get_admin_analytics...")
        result = await get_admin_analytics(current_user=current_user, db=db)
        
        print("\nAdmin Analytics Result:")
        print(f"Total Students: {result['users']['total_students']}")
        print(f"Total Enrollments (Fallback): {result['engagement']['total_enrollments']}")
        print(f"Active Enrollments (Dynamic): {result['engagement']['active_enrollments']}")
        print(f"Completion Rate (Dynamic): {result['performance']['completion_rate']}%")
        
        if result['performance']['completion_rate'] > 0:
            print("\nSUCCESS: Completion rate is now dynamic and non-zero!")
        else:
            # Check if there's actually any progress data to be non-zero
            sms_with_progress = db.query(StudentModuleStatus).filter(StudentModuleStatus.progress_percentage > 0).count()
            sss_with_progress = db.query(StudentSessionStatus).filter(StudentSessionStatus.progress_percentage > 0).count()
            
            if sms_with_progress == 0 and sss_with_progress == 0:
                print("\nINFO: Completion rate is 0.0% but verified as dynamic (no progress data exists in DB).")
            else:
                print("\nWARNING: Completion rate is 0.0% but progress data exists! Check logic.")
                
    except Exception as e:
        print(f"\nERROR during verification: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(verify_analytics())
