import logging
from database import get_db

logger = logging.getLogger(__name__)


def log_admin_action(admin_id: int, admin_username: str, action_type: str, resource_type: str, resource_id: int = None, details: str = None):
    """Log admin actions for audit trail.
    This function is extracted to avoid circular imports between routers and main app.
    """
    try:
        from database import AdminLog
        db = next(get_db())
        try:
            log_entry = AdminLog(
                admin_id=admin_id,
                admin_username=admin_username,
                action_type=action_type,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details
            )
            db.add(log_entry)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to log admin action: {str(e)}")


def log_presenter_action(presenter_id: int, presenter_username: str, action_type: str, resource_type: str, resource_id: int = None, details: str = None):
    """Log presenter actions for audit trail.
    This function is extracted to avoid circular imports between routers and main app.
    """
    try:
        from database import PresenterLog
        db = next(get_db())
        try:
            log_entry = PresenterLog(
                presenter_id=presenter_id,
                presenter_username=presenter_username,
                action_type=action_type,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details
            )
            db.add(log_entry)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to log presenter action: {str(e)}")
