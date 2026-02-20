import os
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import User, Admin, Presenter, Manager
try:
    from zerobouncesdk import ZeroBounce
except ImportError:
    ZeroBounce = None
from dotenv import load_dotenv


import logging

load_dotenv()
logger = logging.getLogger(__name__)

# Initialize ZeroBounce SDK
ZEROBOUNCE_API_KEY = os.getenv("ZEROBOUNCE_API_KEY")
zb_sdk = ZeroBounce(ZEROBOUNCE_API_KEY) if ZEROBOUNCE_API_KEY and ZeroBounce else None


def normalize_email(email: str) -> str:
    """Normalize email by stripping whitespace and converting to lowercase."""
    if not email:
        return ""
    return email.strip().lower()

def check_email_exists(email: str, db: Session) -> dict:
    """
    Check if an email exists in any of the user role tables.
    Returns a dictionary with existence status and the role found.
    """
    normalized_email = normalize_email(email)
    
    # Check Admins
    if db.query(Admin).filter(func.lower(Admin.email) == normalized_email).first():
        return {"exists": True, "role": "Admin"}
    
    # Check Presenters
    if db.query(Presenter).filter(func.lower(Presenter.email) == normalized_email).first():
        return {"exists": True, "role": "Presenter"}
    
    # Check Managers
    if db.query(Manager).filter(func.lower(Manager.email) == normalized_email).first():
        return {"exists": True, "role": "Manager"}
    
    # Check Users (Student/Faculty)
    user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if user:
        return {"exists": True, "role": user.role}
    
    return {"exists": False, "role": None}

def validate_email_zerobounce(email: str) -> dict:
    """
    Validate email using ZeroBounce SDK.
    Returns a dictionary with validation results.
    """
    if not zb_sdk:
        logger.warning("ZeroBounce API key not found. Skipping validation.")
        return {"status": "skipped", "message": "API key not configured", "valid": True}
    
    try:
        response = zb_sdk.validate(email)
        # ZeroBounce status codes: valid, invalid, catch-all, unknown, abuse, spamtrap, mailbox_full
        result = {
            "status": response.status.value if hasattr(response.status, 'value') else response.status,
            "sub_status": response.sub_status.value if hasattr(response.sub_status, 'value') else response.sub_status,
            "valid": response.status == "valid" or response.status == "catch-all",
            "message": f"Email is {response.status}"
        }
        return result
    except Exception as e:
        logger.error(f"ZeroBounce validation error for {email}: {str(e)}")
        return {"status": "error", "message": str(e), "valid": True} # Default to True on error to not block users
