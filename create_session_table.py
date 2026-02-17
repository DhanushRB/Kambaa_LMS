#!/usr/bin/env python3
"""
Script to create the user_sessions table for single device login
"""

from sqlalchemy import create_engine
from session_models import Base
from database import DATABASE_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_session_table():
    """Create the user_sessions table"""
    try:
        engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(bind=engine)
        logger.info("Successfully created user_sessions table")
        return True
    except Exception as e:
        logger.error(f"Failed to create user_sessions table: {str(e)}")
        return False

if __name__ == "__main__":
    create_session_table()