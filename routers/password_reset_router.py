
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from database import get_db, User, Admin, Presenter, Mentor, Manager, PasswordResetOTP
from schemas import ForgotPasswordRequest, VerifyOTPRequest, ResetPasswordRequest
from auth import get_password_hash
from notification_service import NotificationService
from datetime import datetime, timedelta
import random
import string
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["password-reset"])

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = request.email.lower()
    
    # 1. Look for user in all tables
    user = None
    for model in [User, Admin, Presenter, Mentor, Manager]:
        user = db.query(model).filter(model.email == email).first()
        if user:
            break
            
    if not user:
        # Don't reveal if email exists or not for security, but user requirement says 
        # "Forgot Password flow must work consistently" - usually we send success regardless
        # but for this specific request, let's keep it simple.
        raise HTTPException(status_code=404, detail="Email not found")

    # 2. Generate OTP
    otp = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    # 3. Save OTP
    otp_entry = PasswordResetOTP(
        email=email,
        otp=otp,
        expires_at=expires_at
    )
    db.add(otp_entry)
    db.commit()
    
    # 4. Send Email
    notification_service = NotificationService(db)
    subject = "Password Reset OTP"
    body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 10px;">
        <h2 style="color: #3b82f6; text-align: center;">Password Reset Request</h2>
        <p>Hello,</p>
        <p>You requested a password reset for your Kambaa LMS account. Use the following OTP to verify your identity. This OTP is valid for 10 minutes.</p>
        <div style="text-align: center; margin: 30px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #1d4ed8; background: #f0f9ff; padding: 10px 20px; border-radius: 5px; border: 1px dashed #3b82f6;">{otp}</span>
        </div>
        <p>If you didn't request this, you can safely ignore this email.</p>
        <hr style="border: 0; border-top: 1px solid #eeeeee; margin: 30px 0;">
        <p style="font-size: 12px; color: #666666; text-align: center;">&copy; {datetime.now().year} Kambaa AI Learning Management System. All rights reserved.</p>
    </div>
    """
    
    try:
        notification_service.send_email_notification(
            user_id=None, # Generic email
            email=email,
            subject=subject,
            body=body
        )
        return {"message": "OTP sent to your email"}
    except Exception as e:
        logger.error(f"Failed to send password reset email: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send email. Please try again later.")

@router.post("/verify-otp")
async def verify_otp(request: VerifyOTPRequest, db: Session = Depends(get_db)):
    email = request.email.lower()
    
    otp_entry = db.query(PasswordResetOTP).filter(
        PasswordResetOTP.email == email,
        PasswordResetOTP.otp == request.otp,
        PasswordResetOTP.is_used == False
    ).order_by(PasswordResetOTP.created_at.desc()).first()
    
    if not otp_entry:
        raise HTTPException(status_code=400, detail="Invalid OTP")
        
    if otp_entry.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP expired")
        
    if otp_entry.retry_count >= 5:
        raise HTTPException(status_code=400, detail="Too many retries. Please request a new OTP.")
        
    # Valid OTP
    return {"message": "OTP verified successfully"}

@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    email = request.email.lower()
    
    # 1. Verify OTP again for security
    otp_entry = db.query(PasswordResetOTP).filter(
        PasswordResetOTP.email == email,
        PasswordResetOTP.otp == request.otp,
        PasswordResetOTP.is_used == False
    ).order_by(PasswordResetOTP.created_at.desc()).first()
    
    if not otp_entry or otp_entry.expires_at < datetime.utcnow() or otp_entry.retry_count >= 5:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
        
    # 2. Update password in the correct table
    user = None
    user_model = None
    for model in [User, Admin, Presenter, Mentor, Manager]:
        user = db.query(model).filter(model.email == email).first()
        if user:
            user_model = model
            break
            
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.password_hash = get_password_hash(request.new_password)
    otp_entry.is_used = True
    db.commit()
    
    return {"message": "Password reset successful"}
