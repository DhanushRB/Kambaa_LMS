from database import SessionLocal, SystemSettings
import json

db = SessionLocal()
try:
    settings = db.query(SystemSettings).all()
    for setting in settings:
        print(f"Key: {setting.setting_key}, Value: {setting.setting_value}, Category: {setting.setting_category}")
finally:
    db.close()
