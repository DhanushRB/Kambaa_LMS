import logging
import threading
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal
from smtp_models import SMTPConfig
from smtp_endpoints import decrypt_password

logger = logging.getLogger(__name__)

class SMTPConfigCache:
    """Thread-safe SMTP configuration cache to avoid repeated database queries and decryption"""
    
    def __init__(self):
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_duration = timedelta(minutes=30)  # Cache for 30 minutes
        self._lock = threading.Lock()
    
    def get_smtp_config(self) -> Optional[Dict[str, Any]]:
        """Get cached SMTP configuration or fetch from database"""
        with self._lock:
            now = datetime.utcnow()
            
            # Check if cache is valid
            if (self._cache is not None and 
                self._cache_timestamp is not None and 
                now - self._cache_timestamp < self._cache_duration):
                return self._cache
            
            # Cache expired or doesn't exist, fetch from database
            return self._refresh_cache()
    
    def _refresh_cache(self) -> Optional[Dict[str, Any]]:
        """Refresh cache from database"""
        try:
            db = SessionLocal()
            try:
                smtp_config = db.query(SMTPConfig).filter(SMTPConfig.is_active == True).first()
                if not smtp_config:
                    logger.warning("No active SMTP configuration found")
                    self._cache = None
                    self._cache_timestamp = None
                    return None
                
                # Use consistent decryption method
                try:
                    decrypted_password = decrypt_password(smtp_config.smtp_password)
                    logger.info(f"SMTP password processed for {smtp_config.smtp_username}")
                except Exception as e:
                    logger.warning(f"Password decryption failed: {str(e)}")
                    decrypted_password = smtp_config.smtp_password
                
                # Cache the configuration
                self._cache = {
                    'smtp_host': smtp_config.smtp_host,
                    'smtp_port': smtp_config.smtp_port,
                    'smtp_username': smtp_config.smtp_username,
                    'smtp_password': decrypted_password,
                    'smtp_from_email': smtp_config.smtp_from_email,
                    'smtp_from_name': smtp_config.smtp_from_name,
                    'use_tls': smtp_config.use_tls,
                    'use_ssl': smtp_config.use_ssl,
                    'is_active': smtp_config.is_active
                }
                self._cache_timestamp = datetime.utcnow()
                
                return self._cache
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to refresh SMTP cache: {str(e)}")
            self._cache = None
            self._cache_timestamp = None
            return None
    
    def invalidate_cache(self):
        """Invalidate the cache to force refresh on next access"""
        with self._lock:
            self._cache = None
            self._cache_timestamp = None
            logger.info("SMTP configuration cache invalidated")
    
    def is_cache_valid(self) -> bool:
        """Check if cache is valid"""
        with self._lock:
            if self._cache is None or self._cache_timestamp is None:
                return False
            return datetime.utcnow() - self._cache_timestamp < self._cache_duration

# Global cache instance
smtp_cache = SMTPConfigCache()