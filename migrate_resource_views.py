"""
Migration script to add resource_type field to resource_views table.
"""
from database import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Add resource_type column to resource_views table"""
    try:
        with engine.connect() as conn:
            logger.info("Adding resource_type column to resource_views...")
            try:
                conn.execute(text("""
                    ALTER TABLE resource_views 
                    ADD COLUMN resource_type VARCHAR(50) DEFAULT 'RESOURCE'
                """))
                conn.commit()
                logger.info("✓ resource_type column added")
            except Exception as e:
                if "Duplicate column name" in str(e) or "already exists" in str(e).lower():
                    logger.info("✓ resource_type column already exists")
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