import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal, EmailCampaign

logger = logging.getLogger(__name__)

class CampaignScheduler:
    def __init__(self):
        self.running = False
        
    async def start_scheduler(self):
        """Start the campaign scheduler"""
        self.running = True
        logger.info("Campaign scheduler started")
        
        while self.running:
            try:
                await self.check_scheduled_campaigns()
                # Check every minute
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Scheduler error: {str(e)}")
                await asyncio.sleep(60)
    
    async def check_scheduled_campaigns(self):
        """Check for campaigns that need to be sent"""
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            logger.info(f"[SCHEDULER] Checking scheduled campaigns at {now}")
            
            # Find campaigns scheduled to be sent now or in the past
            scheduled_campaigns = db.query(EmailCampaign).filter(
                EmailCampaign.status == "scheduled",
                EmailCampaign.scheduled_time <= now,
                EmailCampaign.scheduled_time.isnot(None)
            ).all()
            
            logger.info(f"[SCHEDULER] Found {len(scheduled_campaigns)} campaigns ready to send")
            
            # Also log all scheduled campaigns for debugging
            all_scheduled_campaigns = db.query(EmailCampaign).filter(
                EmailCampaign.status == "scheduled",
                EmailCampaign.scheduled_time.isnot(None)
            ).all()
            
            logger.info(f"[SCHEDULER] Total scheduled campaigns: {len(all_scheduled_campaigns)}")
            
            for campaign in all_scheduled_campaigns:
                time_diff = campaign.scheduled_time - now
                is_ready = campaign.scheduled_time <= now
                logger.info(f"[SCHEDULER] Campaign {campaign.id}: {campaign.name} scheduled for {campaign.scheduled_time} (diff: {time_diff}, ready: {is_ready})")
            
            for campaign in scheduled_campaigns:
                try:
                    logger.info(f"[SCHEDULER] Sending scheduled campaign: {campaign.name} (ID: {campaign.id})")
                    
                    # Send the campaign (this will update status to sending/completed)
                    await self.send_scheduled_campaign(campaign.id, db)
                    
                except Exception as e:
                    logger.error(f"[SCHEDULER] Failed to send scheduled campaign {campaign.id}: {str(e)}")
                    campaign.status = "failed"
                    db.commit()
                    
        except Exception as e:
            logger.error(f"[SCHEDULER] Error checking scheduled campaigns: {str(e)}")
        finally:
            db.close()
    
    async def send_scheduled_campaign(self, campaign_id: int, db: Session):
        """Send a scheduled campaign"""
        from notification_service import NotificationService
        from database import EmailTemplate, EmailRecipient, User, Admin, Presenter, Mentor, UserCohort
        
        try:
            # Get campaign
            campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return
            
            # Get template
            template = db.query(EmailTemplate).filter(EmailTemplate.id == campaign.template_id).first()
            if not template:
                logger.error(f"Template {campaign.template_id} not found for campaign {campaign_id}")
                return
            
            # Get target users based on target_role
            target_users = []
            
            # Check if target_role is a cohort (starts with "cohort_")
            if campaign.target_role.startswith("cohort_"):
                try:
                    cohort_id = int(campaign.target_role.replace("cohort_", ""))
                    # Get users in this specific cohort
                    user_cohorts = db.query(UserCohort).filter(UserCohort.cohort_id == cohort_id).all()
                    for uc in user_cohorts:
                        user = db.query(User).filter(User.id == uc.user_id).first()
                        if user:
                            target_users.append(user)
                    logger.info(f"Found {len(target_users)} users in cohort {cohort_id}")
                except ValueError:
                    logger.error(f"Invalid cohort ID in target_role: {campaign.target_role}")
                    return
            else:
                # Regular role-based targeting
                if campaign.target_role == "Student":
                    target_users = db.query(User).filter(User.role == "Student").all()
                elif campaign.target_role == "Admin":
                    target_users = db.query(Admin).all()
                elif campaign.target_role == "Presenter":
                    target_users = db.query(Presenter).all()
                elif campaign.target_role == "Mentor":
                    target_users = db.query(Mentor).all()
                elif campaign.target_role == "All":
                    users = db.query(User).all()
                    admins = db.query(Admin).all()
                    presenters = db.query(Presenter).all()
                    mentors = db.query(Mentor).all()
                    target_users = users + admins + presenters + mentors
            
            if not target_users:
                logger.warning(f"No target users found for campaign {campaign_id} with target_role {campaign.target_role}")
                campaign.status = "completed"
                campaign.sent_count = 0
                campaign.completed_at = datetime.utcnow()
                db.commit()
                return
            
            # Update campaign status to sending
            campaign.status = "sending"
            campaign.started_at = datetime.utcnow()
            db.commit()
            
            # Create recipients and send emails
            service = NotificationService(db)
            sent_count = 0
            
            for user in target_users:
                if user.email:
                    try:
                        # Create recipient record
                        recipient = EmailRecipient(
                            campaign_id=campaign.id,
                            user_id=getattr(user, 'id', None),
                            email=user.email,
                            status="pending"
                        )
                        db.add(recipient)
                        
                        # Send email
                        email_body = template.body.replace("{username}", getattr(user, 'username', user.email))
                        email_body = email_body.replace("{email}", user.email)
                        
                        # Send email using regular method
                        email_log = service.send_email_notification(
                            user_id=getattr(user, 'id', None),
                            email=user.email,
                            subject=template.subject,
                            body=email_body
                        )
                        
                        if email_log.status in ["sent", "queued"]:
                            recipient.status = "sent"
                            recipient.sent_at = datetime.utcnow()
                            sent_count += 1
                        else:
                            recipient.status = "failed"
                            recipient.error_message = email_log.error_message
                        
                    except Exception as e:
                        logger.error(f"Failed to send email to {user.email}: {str(e)}")
                        if 'recipient' in locals():
                            recipient.status = "failed"
                            recipient.error_message = str(e)
            
            # Update campaign with final counts and mark as completed
            campaign.sent_count = sent_count
            campaign.status = "completed"
            campaign.completed_at = datetime.utcnow()
            
            db.commit()
            
            logger.info(f"Scheduled campaign {campaign_id} sent to {sent_count} recipients")
            
        except Exception as e:
            logger.error(f"Error sending scheduled campaign {campaign_id}: {str(e)}")
            # Mark campaign as failed
            try:
                campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
                if campaign:
                    campaign.status = "failed"
                    db.commit()
            except:
                pass
    
    def stop_scheduler(self):
        """Stop the campaign scheduler"""
        self.running = False
        logger.info("Campaign scheduler stopped")

# Global scheduler instance
scheduler = CampaignScheduler()

async def start_campaign_scheduler():
    """Start the campaign scheduler as a background task"""
    await scheduler.start_scheduler()

def stop_campaign_scheduler():
    """Stop the campaign scheduler"""
    scheduler.stop_scheduler()

async def trigger_scheduler_check():
    """Manually trigger scheduler check for testing"""
    await scheduler.check_scheduled_campaigns()