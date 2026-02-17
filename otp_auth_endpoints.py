from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
import random
import string
from datetime import datetime, timedelta
from database import get_db, User, Admin, Presenter, Mentor
from default_template_service import DefaultTemplateService
from services.email_service import email_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# In-memory OTP storage (in production, use Redis or database)
otp_storage = {}

class OTPRequest(BaseModel):
    email: EmailStr
    purpose: Optional[str] = "verification"  # verification, password_reset, etc.

class OTPVerification(BaseModel):
    email: EmailStr
    otp_code: str

def generate_otp(length: int = 6) -> str:
    """Generate a random OTP code"""
    return ''.join(random.choices(string.digits, k=length))

def store_otp(email: str, otp_code: str, expires_in_minutes: int = 10):
    """Store OTP with expiration time"""
    expiry_time = datetime.utcnow() + timedelta(minutes=expires_in_minutes)
    otp_storage[email] = {
        'code': otp_code,
        'expires_at': expiry_time,
        'attempts': 0
    }

def verify_otp(email: str, provided_code: str) -> bool:
    """Verify OTP code"""
    if email not in otp_storage:
        return False
    
    stored_otp = otp_storage[email]
    
    # Check if OTP has expired
    if datetime.utcnow() > stored_otp['expires_at']:
        del otp_storage[email]
        return False
    
    # Check attempts limit
    if stored_otp['attempts'] >= 3:
        del otp_storage[email]
        return False
    
    # Verify code
    if stored_otp['code'] == provided_code:
        del otp_storage[email]  # Remove OTP after successful verification
        return True
    else:
        stored_otp['attempts'] += 1
        return False

@router.post("/send-otp")
async def send_otp(
    otp_request: OTPRequest,
    db: Session = Depends(get_db)
):
    """Send OTP to user's email using default template"""
    try:
        # Find user in any table
        user = None
        username = ""
        
        # Check User table (Students/Faculty)
        user_check = db.query(User).filter(User.email == otp_request.email).first()
        if user_check:
            user = user_check
            username = user_check.username
        else:
            # Check Admin table
            admin_check = db.query(Admin).filter(Admin.email == otp_request.email).first()
            if admin_check:
                user = admin_check
                username = admin_check.username
            else:
                # Check Presenter table
                presenter_check = db.query(Presenter).filter(Presenter.email == otp_request.email).first()
                if presenter_check:
                    user = presenter_check
                    username = presenter_check.username
                else:
                    # Check Mentor table
                    mentor_check = db.query(Mentor).filter(Mentor.email == otp_request.email).first()
                    if mentor_check:
                        user = mentor_check
                        username = mentor_check.username
        
        if not user:
            # For security, don't reveal if email exists or not
            return {
                "message": "If the email exists in our system, an OTP has been sent.",
                "status": "sent"
            }
        
        # Generate OTP
        otp_code = generate_otp()
        
        # Store OTP
        store_otp(otp_request.email, otp_code)
        
        # Prepare user data for template
        user_data = {
            'username': username,
            'email': otp_request.email,
            'otp_code': otp_code
        }
        
        # Send OTP email using default template
        success = DefaultTemplateService.send_otp_email(db, user_data, email_service)
        
        if success:
            logger.info(f"OTP sent successfully to {otp_request.email}")
            return {
                "message": "OTP has been sent to your email address.",
                "status": "sent",
                "expires_in": "10 minutes"
            }
        else:
            logger.error(f"Failed to send OTP to {otp_request.email}")
            # Fallback: try to send without template
            try:
                fallback_success = email_service.send_email(
                    to_email=otp_request.email,
                    subject="Your Kamba LMS Verification Code",
                    body=f"Dear {username},\n\nYour verification code is: {otp_code}\n\nThis code will expire in 10 minutes.\n\nBest regards,\nKamba LMS Team"
                )
                
                if fallback_success:
                    return {
                        "message": "OTP has been sent to your email address.",
                        "status": "sent",
                        "expires_in": "10 minutes"
                    }
            except Exception as fallback_error:
                logger.error(f"Fallback email sending failed: {str(fallback_error)}")
            
            raise HTTPException(status_code=500, detail="Failed to send OTP email")
        
    except Exception as e:
        logger.error(f"Send OTP error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send OTP")

@router.post("/verify-otp")
async def verify_otp_endpoint(
    otp_verification: OTPVerification,
    db: Session = Depends(get_db)
):
    """Verify OTP code"""
    try:
        is_valid = verify_otp(otp_verification.email, otp_verification.otp_code)
        
        if is_valid:
            return {
                "message": "OTP verified successfully",
                "status": "verified",
                "email": otp_verification.email
            }
        else:
            return {
                "message": "Invalid or expired OTP code",
                "status": "invalid"
            }
    
    except Exception as e:
        logger.error(f"Verify OTP error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to verify OTP")

@router.post("/resend-otp")
async def resend_otp(
    otp_request: OTPRequest,
    db: Session = Depends(get_db)
):
    """Resend OTP to user's email"""
    try:
        # Clear existing OTP if any
        if otp_request.email in otp_storage:
            del otp_storage[otp_request.email]
        
        # Send new OTP
        return await send_otp(otp_request, db)
    
    except Exception as e:
        logger.error(f"Resend OTP error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to resend OTP")

@router.get("/otp-status/{email}")
async def get_otp_status(email: str):
    """Get OTP status for an email (for debugging/testing)"""
    try:
        if email in otp_storage:
            stored_otp = otp_storage[email]
            time_remaining = (stored_otp['expires_at'] - datetime.utcnow()).total_seconds()
            
            return {
                "email": email,
                "has_active_otp": True,
                "expires_in_seconds": max(0, int(time_remaining)),
                "attempts_made": stored_otp['attempts'],
                "max_attempts": 3
            }
        else:
            return {
                "email": email,
                "has_active_otp": False
            }
    
    except Exception as e:
        logger.error(f"Get OTP status error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get OTP status")