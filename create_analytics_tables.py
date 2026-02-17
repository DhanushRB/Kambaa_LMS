#!/usr/bin/env python3
"""
Script to create the resource analytics tables
"""

from sqlalchemy import create_engine
from resource_analytics_models import Base
from database import DATABASE_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_analytics_tables():
    """Create the resource analytics tables"""
    try:
        engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(bind=engine)
        logger.info("Successfully created resource analytics tables")
        return True
    except Exception as e:
        logger.error(f"Failed to create resource analytics tables: {str(e)}")
        return False

if __name__ == "__main__":
    create_analytics_tables()