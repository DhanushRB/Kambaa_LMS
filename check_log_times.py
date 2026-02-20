from database import SessionLocal, AdminLog, PresenterLog, MentorLog, StudentLog
from datetime import datetime

def check_logs():
    db = SessionLocal()
    try:
        print(f"Current UTC: {datetime.utcnow()}")
        
        # Check AdminLogs
        admin_log = db.query(AdminLog).order_by(AdminLog.timestamp.desc()).first()
        if admin_log:
            print(f"Last AdminLog: id={admin_log.id}, user={admin_log.admin_username}, time={admin_log.timestamp}, type={type(admin_log.timestamp)}")
            
        # Check StudentLogs
        student_log = db.query(StudentLog).order_by(StudentLog.timestamp.desc()).first()
        if student_log:
            print(f"Last StudentLog: id={student_log.id}, user={student_log.student_username}, time={student_log.timestamp}, type={type(student_log.timestamp)}")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_logs()
