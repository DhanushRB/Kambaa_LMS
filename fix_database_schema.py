"""
Final fix script for database schema issues.
Drops foreign key constraints on status tables to allow cohort course tracking.
Adds the missing progress_percentage column.
"""
from database import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_schema():
    """Drop FKs and add missing columns"""
    try:
        with engine.connect() as conn:
            # 1. Drop constraints from student_session_statuses
            logger.info("Dropping foreign keys from student_session_statuses...")
            try:
                # Try common constraint names
                constraints = ['student_session_status_ibfk_2', 'student_session_statuses_ibfk_2']
                for constraint in constraints:
                    try:
                        conn.execute(text(f"ALTER TABLE student_session_statuses DROP FOREIGN KEY {constraint}"))
                        conn.commit()
                        logger.info(f"✓ Dropped {constraint}")
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Could not drop FKs for session status: {str(e)}")

            # 2. Drop constraints from student_module_statuses
            logger.info("Dropping foreign keys from student_module_statuses...")
            try:
                constraints = ['student_module_status_ibfk_2', 'student_module_statuses_ibfk_2']
                for constraint in constraints:
                    try:
                        conn.execute(text(f"ALTER TABLE student_module_statuses DROP FOREIGN KEY {constraint}"))
                        conn.commit()
                        logger.info(f"✓ Dropped {constraint}")
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Could not drop FKs for module status: {str(e)}")

            # 3. Add progress_percentage to student_session_statuses
            logger.info("Adding progress_percentage to student_session_statuses...")
            try:
                conn.execute(text("ALTER TABLE student_session_statuses ADD COLUMN progress_percentage FLOAT DEFAULT 0.0"))
                conn.commit()
                logger.info("✓ progress_percentage added to session status")
            except Exception as e:
                if "Duplicate column name" in str(e) or "already exists" in str(e).lower():
                    logger.info("✓ progress_percentage already exists in session status")
                else:
                    logger.error(f"Error adding progress_percentage: {str(e)}")

            # 4. Add progress_percentage to student_module_statuses
            logger.info("Adding progress_percentage to student_module_statuses...")
            try:
                conn.execute(text("ALTER TABLE student_module_statuses ADD COLUMN progress_percentage FLOAT DEFAULT 0.0"))
                conn.commit()
                logger.info("✓ progress_percentage added to module status")
            except Exception as e:
                if "Duplicate column name" in str(e) or "already exists" in str(e).lower():
                    logger.info("✓ progress_percentage already exists in module status")
                else:
                    logger.error(f"Error adding progress_percentage: {str(e)}")

            # 5. Ensure session_type and module_type exist (idempotent)
            try:
                conn.execute(text("ALTER TABLE student_session_statuses ADD COLUMN session_type VARCHAR(20) DEFAULT 'global'"))
                conn.commit()
            except Exception: pass
            
            try:
                conn.execute(text("ALTER TABLE student_module_statuses ADD COLUMN module_type VARCHAR(20) DEFAULT 'global'"))
                conn.commit()
            except Exception: pass

            # 6. Final verification - update any null values
            conn.execute(text("UPDATE student_session_statuses SET progress_percentage = 0.0 WHERE progress_percentage IS NULL"))
            conn.execute(text("UPDATE student_module_statuses SET progress_percentage = 0.0 WHERE progress_percentage IS NULL"))
            conn.execute(text("UPDATE student_session_statuses SET session_type = 'global' WHERE session_type IS NULL OR session_type = ''"))
            conn.execute(text("UPDATE student_module_statuses SET module_type = 'global' WHERE module_type IS NULL OR module_type = ''"))
            conn.commit()

        logger.info("Database fix completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Fix failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = fix_schema()
    if success:
        print("\n✅ Database schema fixed successfully!")
    else:
        print("\n❌ Database fix failed. Check logs.")
