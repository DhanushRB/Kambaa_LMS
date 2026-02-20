from database import SessionLocal, AdminLog, PresenterLog, StudentLog, MentorLog, EmailLog
import logging

logger = logging.getLogger(__name__)

def log_admin_action(admin_id: int, admin_username: str, action_type: str, resource_type: str, resource_id: int = None, details: str = None, ip_address: str = None):
    """Log admin actions for audit trail"""
    db = SessionLocal()
    try:
        log_entry = AdminLog(
            admin_id=admin_id,
            admin_username=admin_username,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log admin action: {str(e)}")
    finally:
        db.close()

def log_presenter_action(presenter_id: int, presenter_username: str, action_type: str, resource_type: str, resource_id: int = None, details: str = None, ip_address: str = None):
    """Log presenter actions for audit trail"""
    db = SessionLocal()
    try:
        log_entry = PresenterLog(
            presenter_id=presenter_id,
            presenter_username=presenter_username,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log presenter action: {str(e)}")
    finally:
        db.close()

def log_student_action(student_id: int, student_username: str, action_type: str, resource_type: str, resource_id: int = None, details: str = None, ip_address: str = None):
    """Log student actions for audit trail"""
    db = SessionLocal()
    try:
        log_entry = StudentLog(
            student_id=student_id,
            student_username=student_username,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log student action: {str(e)}")
    finally:
        db.close()

def log_mentor_action(mentor_id: int, mentor_username: str, action_type: str, resource_type: str, resource_id: int = None, details: str = None, ip_address: str = None):
    """Log mentor actions for audit trail"""
    db = SessionLocal()
    try:
        log_entry = MentorLog(
            mentor_id=mentor_id,
            mentor_username=mentor_username,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log mentor action: {str(e)}")
    finally:
        db.close()
