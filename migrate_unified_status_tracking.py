"""
Migration script to add session_type and module_type fields to status tracking tables.
This enables unified tracking for both global and cohort-specific courses.
"""
from database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from sqlalchemy import text

def migrate():
    """Add type columns to existing status tables"""
    try:
        with engine.connect() as conn:
            # Add session_type to student_session_statuses
            logger.info("Adding session_type column to student_session_statuses...")
            try:
                conn.execute(text("""
                    ALTER TABLE student_session_statuses 
                    ADD COLUMN session_type VARCHAR(20) DEFAULT 'global'
                """))
                conn.commit()
                logger.info("✓ session_type column added")
            except Exception as e:
                if "Duplicate column name" in str(e) or "already exists" in str(e).lower():
                    logger.info("✓ session_type column already exists")
                else:
                    raise
            
            # Add module_type to student_module_statuses
            logger.info("Adding module_type column to student_module_statuses...")
            try:
                conn.execute(text("""
                    ALTER TABLE student_module_statuses 
                    ADD COLUMN module_type VARCHAR(20) DEFAULT 'global'
                """))
                conn.commit()
                logger.info("✓ module_type column added")
            except Exception as e:
                if "Duplicate column name" in str(e) or "already exists" in str(e).lower():
                    logger.info("✓ module_type column already exists")
                else:
                    raise
            
            # Update existing records to have 'global' type (if not already set)
            logger.info("Updating existing records to 'global' type...")
            conn.execute(text("""
                UPDATE student_session_statuses 
                SET session_type = 'global' 
                WHERE session_type IS NULL OR session_type = ''
            """))
            conn.execute(text("""
                UPDATE student_module_statuses 
                SET module_type = 'global' 
                WHERE module_type IS NULL OR module_type = ''
            """))
            conn.commit()
            logger.info("✓ Existing records updated")
            
        logger.info("Migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = migrate()
    if success:
        print("\n✅ Migration completed successfully!")
        print("Status tracking now supports both global and cohort courses.")
    else:
        print("\n❌ Migration failed. Check logs for details.")
