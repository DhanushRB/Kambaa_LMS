from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, SystemSettings
from auth import get_current_admin_or_presenter
from pydantic import BaseModel
from typing import Dict, Any
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system-settings", tags=["System Settings"])

class SystemSettingUpdate(BaseModel):
    setting_key: str
    setting_value: Dict[str, Any]
    setting_category: str

class MeetingSettingsUpdate(BaseModel):
    meetingAutoLockEnabled: bool = True
    meetingAutoLockMinutes: int = 10
    meetingExtensionAllowed: bool = True
    meetingMaxExtensionMinutes: int = 30

class GeneralSettingsUpdate(BaseModel):
    siteName: str = ""
    timezone: str = "UTC"
    siteDescription: str = ""
    dateFormat: str = "YYYY-MM-DD"
    language: str = "en"

class SecuritySettingsUpdate(BaseModel):
    passwordMinLength: int = 8
    sessionTimeout: int = 60
    passwordRequireSpecialChars: bool = False
    passwordRequireNumbers: bool = False
    passwordRequireUppercase: bool = False
    twoFactorAuth: bool = False

class MonitoringSettingsUpdate(BaseModel):
    activityLogging: bool = False
    performanceMonitoring: bool = False
    errorReporting: bool = False
    debugMode: bool = False

class CommunicationSettingsUpdate(BaseModel):
    smsNotifications: bool = False
    pushNotifications: bool = False
    emailDigest: bool = False
    weeklyReports: bool = False

@router.get("/meeting")
async def get_meeting_settings(
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get meeting settings"""
    try:
        setting = db.query(SystemSettings).filter(
            SystemSettings.setting_key == "meeting_settings"
        ).first()
        
        if setting:
            return json.loads(setting.setting_value)
        else:
            # Return default settings
            return {
                "meetingAutoLockEnabled": True,
                "meetingAutoLockMinutes": 10,
                "meetingExtensionAllowed": True,
                "meetingMaxExtensionMinutes": 30
            }
    except Exception as e:
        logger.error(f"Get meeting settings error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get meeting settings")

@router.post("/meeting")
async def save_meeting_settings(
    settings: MeetingSettingsUpdate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Save meeting settings"""
    try:
        # Check if setting exists
        existing_setting = db.query(SystemSettings).filter(
            SystemSettings.setting_key == "meeting_settings"
        ).first()
        
        settings_dict = settings.dict()
        
        if existing_setting:
            # Update existing setting
            existing_setting.setting_value = json.dumps(settings_dict)
            existing_setting.updated_by = current_user.id
        else:
            # Create new setting
            new_setting = SystemSettings(
                setting_key="meeting_settings",
                setting_value=json.dumps(settings_dict),
                setting_category="meeting",
                updated_by=current_user.id
            )
            db.add(new_setting)
        
        db.commit()
        
        return {"message": "Meeting settings saved successfully", "settings": settings_dict}
    except Exception as e:
        db.rollback()
        logger.error(f"Save meeting settings error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save meeting settings")

@router.put("/meeting")
async def update_meeting_settings(
    settings: MeetingSettingsUpdate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Update meeting settings (PUT method)"""
    try:
        # Check if setting exists
        existing_setting = db.query(SystemSettings).filter(
            SystemSettings.setting_key == "meeting_settings"
        ).first()
        
        settings_dict = settings.dict()
        
        if existing_setting:
            # Update existing setting
            existing_setting.setting_value = json.dumps(settings_dict)
            existing_setting.updated_by = current_user.id
        else:
            # Create new setting
            new_setting = SystemSettings(
                setting_key="meeting_settings",
                setting_value=json.dumps(settings_dict),
                setting_category="meeting",
                updated_by=current_user.id
            )
            db.add(new_setting)
        
        db.commit()
        
        return {"message": "Meeting settings updated successfully", "settings": settings_dict}
    except Exception as e:
        db.rollback()
        logger.error(f"Update meeting settings error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update meeting settings")

@router.get("/all")
async def get_all_settings(
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Get all system settings"""
    try:
        settings = db.query(SystemSettings).all()
        
        result = {}
        for setting in settings:
            try:
                result[setting.setting_key] = json.loads(setting.setting_value)
            except:
                result[setting.setting_key] = setting.setting_value
        
        return result
    except Exception as e:
        logger.error(f"Get all settings error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get settings")

@router.post("/save")
async def save_system_setting(
    setting: SystemSettingUpdate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Save a system setting"""
    try:
        # Check if setting exists
        existing_setting = db.query(SystemSettings).filter(
            SystemSettings.setting_key == setting.setting_key
        ).first()
        
        if existing_setting:
            # Update existing setting
            existing_setting.setting_value = json.dumps(setting.setting_value)
            existing_setting.setting_category = setting.setting_category
            existing_setting.updated_by = current_user.id
        else:
            # Create new setting
            new_setting = SystemSettings(
                setting_key=setting.setting_key,
                setting_value=json.dumps(setting.setting_value),
                setting_category=setting.setting_category,
                updated_by=current_user.id
            )
            db.add(new_setting)
        
        db.commit()
        
        return {"message": f"Setting '{setting.setting_key}' saved successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Save system setting error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save setting")

# Additional endpoints for other settings categories
@router.put("/general")
async def update_general_settings(
    settings: GeneralSettingsUpdate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Update general settings"""
    try:
        existing_setting = db.query(SystemSettings).filter(
            SystemSettings.setting_key == "general_settings"
        ).first()
        
        settings_dict = settings.dict()
        
        if existing_setting:
            existing_setting.setting_value = json.dumps(settings_dict)
            existing_setting.updated_by = current_user.id
        else:
            new_setting = SystemSettings(
                setting_key="general_settings",
                setting_value=json.dumps(settings_dict),
                setting_category="general",
                updated_by=current_user.id
            )
            db.add(new_setting)
        
        db.commit()
        return {"message": "General settings updated successfully", "settings": settings_dict}
    except Exception as e:
        db.rollback()
        logger.error(f"Update general settings error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update general settings")

@router.put("/security")
async def update_security_settings(
    settings: SecuritySettingsUpdate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Update security settings"""
    try:
        existing_setting = db.query(SystemSettings).filter(
            SystemSettings.setting_key == "security_settings"
        ).first()
        
        settings_dict = settings.dict()
        
        if existing_setting:
            existing_setting.setting_value = json.dumps(settings_dict)
            existing_setting.updated_by = current_user.id
        else:
            new_setting = SystemSettings(
                setting_key="security_settings",
                setting_value=json.dumps(settings_dict),
                setting_category="security",
                updated_by=current_user.id
            )
            db.add(new_setting)
        
        db.commit()
        return {"message": "Security settings updated successfully", "settings": settings_dict}
    except Exception as e:
        db.rollback()
        logger.error(f"Update security settings error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update security settings")

@router.put("/monitoring")
async def update_monitoring_settings(
    settings: MonitoringSettingsUpdate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Update monitoring settings"""
    try:
        existing_setting = db.query(SystemSettings).filter(
            SystemSettings.setting_key == "monitoring_settings"
        ).first()
        
        settings_dict = settings.dict()
        
        if existing_setting:
            existing_setting.setting_value = json.dumps(settings_dict)
            existing_setting.updated_by = current_user.id
        else:
            new_setting = SystemSettings(
                setting_key="monitoring_settings",
                setting_value=json.dumps(settings_dict),
                setting_category="monitoring",
                updated_by=current_user.id
            )
            db.add(new_setting)
        
        db.commit()
        return {"message": "Monitoring settings updated successfully", "settings": settings_dict}
    except Exception as e:
        db.rollback()
        logger.error(f"Update monitoring settings error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update monitoring settings")

@router.put("/communication")
async def update_communication_settings(
    settings: CommunicationSettingsUpdate,
    current_user = Depends(get_current_admin_or_presenter),
    db: Session = Depends(get_db)
):
    """Update communication settings"""
    try:
        existing_setting = db.query(SystemSettings).filter(
            SystemSettings.setting_key == "communication_settings"
        ).first()
        
        settings_dict = settings.dict()
        
        if existing_setting:
            existing_setting.setting_value = json.dumps(settings_dict)
            existing_setting.updated_by = current_user.id
        else:
            new_setting = SystemSettings(
                setting_key="communication_settings",
                setting_value=json.dumps(settings_dict),
                setting_category="communication",
                updated_by=current_user.id
            )
            db.add(new_setting)
        
        db.commit()
        return {"message": "Communication settings updated successfully", "settings": settings_dict}
    except Exception as e:
        db.rollback()
        logger.error(f"Update communication settings error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update communication settings")