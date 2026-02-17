from database import engine, Base, StudentSessionStatus, StudentModuleStatus
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    try:
        logger.info("Creating new progress tracking tables...")
        # Create the tables if they don't exist
        # This will only create the new tables because the others already exist and Base.metadata.create_all handles that
        Base.metadata.create_all(bind=engine, tables=[
            StudentSessionStatus.__table__,
            StudentModuleStatus.__table__
        ])
        logger.info("Successfully created student_session_statuses and student_module_statuses tables.")
    except Exception as e:
        logger.error(f"Migration error: {e}")

if __name__ == "__main__":
    migrate()
