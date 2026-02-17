from database import engine, Base, StudentSessionStatus, StudentModuleStatus
from sqlalchemy import inspect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_tables():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info(f"Existing tables: {tables}")
    
    if "student_session_statuses" in tables and "student_module_statuses" in tables:
        logger.info("Progress tracking tables exist.")
        return True
    else:
        logger.error("Progress tracking tables missin!")
        return False

if __name__ == "__main__":
    verify_tables()
