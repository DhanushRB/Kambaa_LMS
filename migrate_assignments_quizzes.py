"""
Migration script to add session_type field to assignments and quizzes tables.
"""
from database import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Add session_type column to assignments and quizzes tables"""
    try:
        with engine.connect() as conn:
            # Add session_type to assignments
            logger.info("Adding session_type column to assignments...")
            try:
                conn.execute(text("""
                    ALTER TABLE assignments 
                    ADD COLUMN session_type VARCHAR(20) DEFAULT 'global'
                """))
                conn.commit()
                logger.info("✓ session_type column added to assignments")
            except Exception as e:
                if "Duplicate column name" in str(e) or "already exists" in str(e).lower():
                    logger.info("✓ session_type column already exists in assignments")
                else:
                    raise
            
            # Add session_type to quizzes
            logger.info("Adding session_type column to quizzes...")
            try:
                conn.execute(text("""
                    ALTER TABLE quizzes 
                    ADD COLUMN session_type VARCHAR(20) DEFAULT 'global'
                """))
                conn.commit()
                logger.info("✓ session_type column added to quizzes")
            except Exception as e:
                if "Duplicate column name" in str(e) or "already exists" in str(e).lower():
                    logger.info("✓ session_type column already exists in quizzes")
                else:
                    raise
            
        logger.info("Migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = migrate()
    if success:
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration failed.")
