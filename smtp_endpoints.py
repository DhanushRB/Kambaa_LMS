"""
SMTP Configuration Endpoints for Admin Settings
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
from typing import Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from cryptography.fernet import Fernet
import os
import base64
import socket

from database import get_db, Admin
from auth import get_current_admin_or_presenter
from smtp_models import SMTPConfig

try:
    from smtp_cache import smtp_cache
except ImportError:
    smtp_cache = None

router = APIRouter(prefix="/admin/settings", tags=["SMTP Settings"])
logger = logging.getLogger(__name__)

# Encryption key for SMTP passwords
ENCRYPTION_KEY = os.getenv("SMTP_ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    # Generate a consistent 32-byte key for development
    ENCRYPTION_KEY = Fernet.generate_key()
    logger.warning("Using generated encryption key. Set SMTP_ENCRYPTION_KEY environment variable for production.")
else:
    if isinstance(ENCRYPTION_KEY, str):
        ENCRYPTION_KEY = ENCRYPTION_KEY.encode()

cipher_suite = Fernet(ENCRYPTION_KEY)

class SMTPConfigCreate(BaseModel):
    smtp_host: str = Field(..., min_length=1)
    smtp_port: int = Field(..., ge=1, le=65535)
    smtp_username: str = Field(..., min_length=1)
    smtp_password: str = Field(..., min_length=1)
    smtp_from_email: str = Field(..., min_length=1)
    smtp_from_name: str = Field(default="Kambaa LMS")
    use_tls: bool = Field(default=True)
    use_ssl: bool = Field(default=False)
    
    @validator('smtp_host')
    def validate_host(cls, v):
        if not v or not v.strip():
            raise ValueError('SMTP host is required')
        return v.strip()
    
    @validator('smtp_from_email')
    def validate_email(cls, v):
        if not v or '@' not in v:
            raise ValueError('Valid email address is required')
        return v.strip()
    
    class Config:
        extra = "ignore"

class SMTPConfigUpdate(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[str] = None
    smtp_from_name: Optional[str] = None
    use_tls: Optional[bool] = None
    use_ssl: Optional[bool] = None

class SMTPTestRequest(BaseModel):
    test_email: str
    subject: str = "SMTP Test Email"
    message: str = "This is a test email from LMS SMTP configuration."

def encrypt_password(password: str) -> str:
    """Encrypt SMTP password with consistent key"""
    key = os.getenv("SMTP_ENCRYPTION_KEY")
    if not key:
        # Store password as plain text if no encryption key
        return password
    
    if isinstance(key, str):
        key = key.encode()
    
    try:
        cipher = Fernet(key)
        return cipher.encrypt(password.encode()).decode()
    except Exception:
        # If encryption fails, store as plain text
        return password

def decrypt_password(encrypted_password: str) -> str:
    """Decrypt SMTP password with consistent key"""
    key = os.getenv("SMTP_ENCRYPTION_KEY")
    if not key:
        # Return as plain text if no encryption key
        return encrypted_password
    
    if isinstance(key, str):
        key = key.encode()
    
    try:
        cipher = Fernet(key)
        return cipher.decrypt(encrypted_password.encode()).decode()
    except Exception:
        # If decryption fails, return as plain text
        return encrypted_password

@router.get("/smtp")
async def get_smtp_config(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get current SMTP configuration (without password)"""
    try:
        config = db.query(SMTPConfig).filter(SMTPConfig.is_active == True).first()
        
        if not config:
            return {"smtp_config": None}
        
        return {
            "smtp_config": {
                "id": config.id,
                "smtp_host": config.smtp_host,
                "smtp_port": config.smtp_port,
                "smtp_username": config.smtp_username,
                "smtp_from_email": config.smtp_from_email,
                "smtp_from_name": config.smtp_from_name,
                "use_tls": config.use_tls,
                "use_ssl": config.use_ssl,
                "created_at": config.created_at,
                "updated_at": config.updated_at
            }
        }
    except Exception as e:
        logger.error(f"Get SMTP config error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch SMTP configuration")

@router.post("/smtp/debug")
async def debug_smtp_data(
    request_data: dict,
    current_admin = Depends(get_current_admin_or_presenter)
):
    """Debug endpoint to see what data is being sent"""
    logger.info(f"SMTP debug data: {request_data}")
    return {"received_data": request_data}

@router.post("/smtp")
async def create_smtp_config(
    config_data: dict,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Create or update SMTP configuration"""
    try:
        # Manual validation to handle any data format
        required_fields = ['smtp_host', 'smtp_port', 'smtp_username', 'smtp_password', 'smtp_from_email']
        for field in required_fields:
            if field not in config_data or not config_data[field]:
                raise HTTPException(status_code=422, detail=f"Field '{field}' is required")
        
        # Validate and convert data
        smtp_host = str(config_data['smtp_host']).strip()
        smtp_port = int(config_data['smtp_port'])
        smtp_username = str(config_data['smtp_username']).strip()
        smtp_password = str(config_data['smtp_password'])
        smtp_from_email = str(config_data['smtp_from_email']).strip()
        smtp_from_name = str(config_data.get('smtp_from_name', 'Kambaa LMS')).strip()
        use_tls = bool(config_data.get('use_tls', True))
        use_ssl = bool(config_data.get('use_ssl', False))
        
        # Basic validation
        if not smtp_host:
            raise HTTPException(status_code=422, detail="SMTP host cannot be empty")
        if not (1 <= smtp_port <= 65535):
            raise HTTPException(status_code=422, detail="SMTP port must be between 1 and 65535")
        if '@' not in smtp_from_email:
            raise HTTPException(status_code=422, detail="Invalid email format")
        
        # Deactivate existing configs
        db.query(SMTPConfig).update({"is_active": False})
        
        # Encrypt password
        encrypted_password = encrypt_password(smtp_password)
        
        # Create new config
        smtp_config = SMTPConfig(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=encrypted_password,
            smtp_from_email=smtp_from_email,
            smtp_from_name=smtp_from_name,
            use_tls=use_tls,
            use_ssl=use_ssl,
            is_active=True
        )
        
        db.add(smtp_config)
        db.commit()
        db.refresh(smtp_config)
        
        # Invalidate cache to force refresh
        if smtp_cache:
            smtp_cache.invalidate_cache()
        
        return {
            "message": "SMTP configuration saved successfully",
            "config_id": smtp_config.id
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create SMTP config error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save SMTP configuration")

@router.put("/smtp/{config_id}")
async def update_smtp_config(
    config_id: int,
    config_data: SMTPConfigUpdate,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Update existing SMTP configuration"""
    try:
        config = db.query(SMTPConfig).filter(SMTPConfig.id == config_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="SMTP configuration not found")
        
        # Update fields
        update_data = config_data.dict(exclude_unset=True)
        
        # Encrypt password if provided
        if 'smtp_password' in update_data:
            update_data['smtp_password'] = encrypt_password(update_data['smtp_password'])
        
        for field, value in update_data.items():
            setattr(config, field, value)
        
        db.commit()
        
        # Invalidate cache to force refresh
        if smtp_cache:
            smtp_cache.invalidate_cache()
        
        return {"message": "SMTP configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update SMTP config error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update SMTP configuration")

@router.post("/smtp/test")
async def test_smtp_config(
    test_data: SMTPTestRequest,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Test SMTP configuration by sending a test email"""
    try:
        config = db.query(SMTPConfig).filter(SMTPConfig.is_active == True).first()
        if not config:
            raise HTTPException(status_code=404, detail="No active SMTP configuration found. Please save the configuration first.")
        
        # Clean and validate hostname
        smtp_host = config.smtp_host.strip()
        
        # Test DNS resolution with more flexible error handling
        try:
            socket.gethostbyname(smtp_host)
        except socket.gaierror as dns_error:
            logger.warning(f"DNS resolution warning for '{smtp_host}': {str(dns_error)}")
        
        # Decrypt password
        try:
            password = decrypt_password(config.smtp_password)
        except Exception as decrypt_error:
            logger.error(f"Password decryption failed: {str(decrypt_error)}")
            raise HTTPException(status_code=500, detail="Failed to decrypt SMTP password. Please reconfigure SMTP settings.")
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = f"{config.smtp_from_name} <{config.smtp_from_email}>"
        msg['To'] = test_data.test_email
        msg['Subject'] = test_data.subject
        
        # Add body
        body = f"""
{test_data.message}

---
This test email was sent from LMS SMTP configuration.
Configuration Details:
- SMTP Host: {config.smtp_host}
- SMTP Port: {config.smtp_port}
- From Email: {config.smtp_from_email}
- TLS: {'Enabled' if config.use_tls else 'Disabled'}
- SSL: {'Enabled' if config.use_ssl else 'Disabled'}

Test performed by: {current_admin.username} ({current_admin.email})
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email with timeout and proper connection management
        server = None
        try:
            # Port 465 requires SSL, other ports typically use TLS
            if config.smtp_port == 465 or config.use_ssl:
                server = smtplib.SMTP_SSL(smtp_host, config.smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(smtp_host, config.smtp_port, timeout=30)
                if config.use_tls:
                    server.starttls()
            
            # Set command timeout
            server.sock.settimeout(30)
            server.login(config.smtp_username, password)
            server.send_message(msg)
            
        except Exception as smtp_error:
            logger.error(f"SMTP connection error: {str(smtp_error)}")
            raise smtp_error
        finally:
            if server:
                try:
                    server.quit()
                except:
                    pass
        
        return {
            "message": f"Test email sent successfully to {test_data.test_email}",
            "test_email": test_data.test_email,
            "smtp_host": config.smtp_host
        }
        
    except HTTPException:
        raise
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"SMTP authentication failed: {str(e)}. Check username and password.")
    except smtplib.SMTPConnectError as e:
        logger.error(f"SMTP connection error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to connect to SMTP server: {str(e)}. Check host and port.")
    except smtplib.SMTPRecipientsRefused as e:
        logger.error(f"SMTP recipients refused: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Recipient email refused: {str(e)}.")
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"SMTP error: {str(e)}")
    except socket.timeout:
        logger.error("SMTP connection timeout")
        raise HTTPException(status_code=408, detail="SMTP connection timeout. Server may be slow or unreachable.")
    except OSError as e:
        logger.error(f"Network error: {str(e)}")
        if "getaddrinfo failed" in str(e) or "Name or service not known" in str(e):
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot connect to SMTP host '{config.smtp_host}'. Please verify: 1) Hostname is correct, 2) Network connectivity, 3) DNS settings."
            )
        else:
            raise HTTPException(status_code=400, detail=f"Network error: {str(e)}")
    except Exception as e:
        logger.error(f"SMTP test error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"SMTP test failed: {str(e)}")

@router.delete("/smtp/{config_id}")
async def delete_smtp_config(
    config_id: int,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Delete SMTP configuration"""
    try:
        config = db.query(SMTPConfig).filter(SMTPConfig.id == config_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="SMTP configuration not found")
        
        db.delete(config)
        db.commit()
        
        # Invalidate cache to force refresh
        if smtp_cache:
            smtp_cache.invalidate_cache()
        
        return {"message": "SMTP configuration deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete SMTP config error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete SMTP configuration")

@router.get("/smtp/status")
async def get_smtp_status(
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get SMTP configuration status and test connectivity"""
    try:
        config = db.query(SMTPConfig).filter(SMTPConfig.is_active == True).first()
        
        if not config:
            return {
                "configured": False,
                "message": "No SMTP configuration found. Please configure SMTP settings first."
            }
        
        # Test basic connectivity (without sending email)
        try:
            import socket
            socket.gethostbyname(config.smtp_host.strip())
            dns_status = "OK"
        except Exception as e:
            dns_status = f"DNS Error: {str(e)}"
        
        return {
            "configured": True,
            "smtp_host": config.smtp_host,
            "smtp_port": config.smtp_port,
            "smtp_username": config.smtp_username,
            "smtp_from_email": config.smtp_from_email,
            "smtp_from_name": config.smtp_from_name,
            "use_tls": config.use_tls,
            "use_ssl": config.use_ssl,
            "dns_status": dns_status,
            "created_at": config.created_at,
            "updated_at": config.updated_at,
            "message": "SMTP configuration is active and ready to use."
        }
    except Exception as e:
        logger.error(f"Get SMTP status error: {str(e)}")
        return {
            "configured": False,
            "error": str(e),
            "message": "Error checking SMTP configuration status."
        }

@router.post("/smtp/send-test-notification")
async def send_test_notification(
    test_data: dict,
    current_admin = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Send a test notification email using the email service"""
    try:
        test_email = test_data.get('test_email')
        if not test_email:
            raise HTTPException(status_code=400, detail="test_email is required")
        
        # Check if SMTP is configured
        config = db.query(SMTPConfig).filter(SMTPConfig.is_active == True).first()
        if not config:
            raise HTTPException(status_code=404, detail="No SMTP configuration found. Please configure SMTP settings first.")
        
        # Import and use the notification function
        try:
            from email_service import send_notification_email
            
            success = send_notification_email(
                to_emails=[test_email],
                subject="Test Notification from LMS",
                message=f"This is a test notification email sent from the LMS dashboard. If you receive this email, your SMTP configuration is working correctly. Test performed by: {current_admin.username}",
                notification_type="info"
            )
            
            if success:
                return {
                    "message": f"Test notification sent successfully to {test_email}",
                    "success": True
                }
            else:
                return {
                    "message": "Failed to send test notification. Please check SMTP configuration and logs.",
                    "success": False
                }
        except ImportError as e:
            logger.error(f"Import error: {str(e)}")
            raise HTTPException(status_code=500, detail="Email service not available")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send test notification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send test notification: {str(e)}")

@router.get("/smtp/presets")
async def get_smtp_presets(
    current_admin = Depends(get_current_admin_or_presenter)
):
    """Get common SMTP configuration presets"""
    return {
        "presets": [
            {
                "name": "Gmail",
                "smtp_host": "smtp.gmail.com",
                "smtp_port": 587,
                "use_tls": True,
                "use_ssl": False,
                "instructions": "Use your Gmail address and App Password (not regular password)"
            },
            {
                "name": "Outlook/Hotmail",
                "smtp_host": "smtp-mail.outlook.com",
                "smtp_port": 587,
                "use_tls": True,
                "use_ssl": False,
                "instructions": "Use your Outlook address and App Password"
            },
            {
                "name": "Yahoo Mail",
                "smtp_host": "smtp.mail.yahoo.com",
                "smtp_port": 587,
                "use_tls": True,
                "use_ssl": False,
                "instructions": "Use your Yahoo address and App Password"
            },
            {
                "name": "Office 365",
                "smtp_host": "smtp.office365.com",
                "smtp_port": 587,
                "use_tls": True,
                "use_ssl": False,
                "instructions": "Use your Office 365 email and password or App Password"
            },
            {
                "name": "Custom Domain",
                "smtp_host": "mail.yourdomain.com",
                "smtp_port": 587,
                "use_tls": True,
                "use_ssl": False,
                "instructions": "Replace with your domain's SMTP server (e.g., mail.yourdomain.com)"
            },
            {
                "name": "Custom SMTP",
                "smtp_host": "",
                "smtp_port": 587,
                "use_tls": True,
                "use_ssl": False,
                "instructions": "Enter any SMTP server details - supports all hostname formats"
            }
        ]
    }