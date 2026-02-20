import os
import sys
from sqlalchemy.orm import Session
from database import SessionLocal, StudentModuleStatus, StudentSessionStatus, Presenter
from presenter_dashboard_router import get_presenter_dashboard
import asyncio
from unittest.mock import MagicMock

async def verify_presenter():
    db = SessionLocal()
    try:
        # Mock presenter
        presenter = db.query(Presenter).first()
        if not presenter:
            print("INFO: No presenters found in DB. Using mock with no cohorts.")
            presenter = MagicMock(id=999)
        
        # Call the router function directly
        print(f"Calling get_presenter_dashboard for presenter ID: {presenter.id}...")
        result = await get_presenter_dashboard(current_presenter=presenter, db=db)
        
        print("\nPresenter Dashboard Result:")
        print(f"Total Students: {result['users']['total_students']}")
        print(f"Completion Rate (Dynamic): {result['performance']['completion_rate']}%")
        print(f"Attendance Rate (Dynamic): {result['performance']['attendance_rate']}%")
        
        if result['performance']['completion_rate'] > 0:
            print("\nSUCCESS: Presenter completion rate is dynamic and non-zero!")
        else:
            print("\nINFO: Presenter completion rate is 0.0% (likely due to no active students in assigned cohorts).")
                
    except Exception as e:
        print(f"\nERROR during verification: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(verify_presenter())
