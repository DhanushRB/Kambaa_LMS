from database import SessionLocal, EmailRecipient, EmailCampaign
from sqlalchemy import func
import logging

db = SessionLocal()

print("--- RECENT CAMPAIGNS ---")
cs = db.query(EmailCampaign).order_by(EmailCampaign.id.desc()).limit(10).all()
for c in cs:
    o = db.query(EmailRecipient).filter(
        EmailRecipient.campaign_id == c.id, 
        EmailRecipient.opened_at.isnot(None)
    ).count()
    cl = db.query(EmailRecipient).filter(
        EmailRecipient.campaign_id == c.id, 
        EmailRecipient.clicked_at.isnot(None)
    ).count()
    print(f"ID: {c.id}, Name: {c.name}, Status: {c.status}, Sent: {c.sent_count}, Opened: {o}, Clicked: {cl}")

print("\n--- OVERALL SUMMARY ---")
total_opened = db.query(EmailRecipient).filter(EmailRecipient.opened_at.isnot(None)).count()
total_clicked = db.query(EmailRecipient).filter(EmailRecipient.clicked_at.isnot(None)).count()
total_sent = db.query(EmailRecipient).filter(EmailRecipient.status == "sent").count()
print(f"Total Sent (Recipients): {total_sent}")
print(f"Total Opened: {total_opened}")
print(f"Total Clicked: {total_clicked}")

db.close()
