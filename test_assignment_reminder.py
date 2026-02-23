import asyncio
import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_assignment_reminder_logic():
    print("\nTesting check_assignment_reminders...")
    
    # Mock DB session
    db = MagicMock()
    
    # 1. Mock Assignment
    now = datetime.utcnow()
    assignment = MagicMock()
    assignment.id = 101
    assignment.title = "Test Assignment 1"
    assignment.due_date = now + timedelta(hours=24)
    assignment.due_reminder_sent = False
    assignment.session_id = 1
    assignment.session_type = "global"
    assignment.is_active = True
    
    # 2. Mock Template
    template = MagicMock()
    template.name = "Assignment Due Reminder"
    template.subject = "Reminder: Assignment '{assignment_title}' is due tomorrow"
    template.body = "Dear {username}, '{assignment_title}' for '{session_title}' is due on {due_date}."
    template.is_active = True
    
    # 3. Mock Students
    # Student 1: Already submitted
    # Student 2: Not submitted
    student1 = MagicMock(id=1, username="student_submitted", email="s1@ex.com")
    student2 = MagicMock(id=2, username="student_pending", email="s2@ex.com")
    
    # Mock Submissions
    submission1 = MagicMock(student_id=1)
    assignment.submissions = [submission1]
    
    # Mock Session and Module
    session = MagicMock(id=1, title="Test Session", module_id=1)
    module = MagicMock(id=1, course_id=1)
    
    # Mock DB query behavior
    def mock_query(model):
        query = MagicMock()
        model_str = str(model)
        
        if "Assignment" in model_str and "AssignmentSubmission" not in model_str:
            query.filter.return_value.all.return_value = [assignment]
        elif "EmailTemplate" in model_str:
            query.filter.return_value.first.return_value = template
        elif "Session" in model_str:
            query.filter.return_value.first.return_value = session
        elif "Module" in model_str:
            query.filter.return_value.first.return_value = module
        elif "User" in model_str:
            # For the student retrieval query
            query.join.return_value.filter.return_value.all.return_value = [student2]
        
        return query

    db.query.side_effect = mock_query
    
    from campaign_scheduler import scheduler
    
    with patch("notification_service.NotificationService.send_email_notification") as mock_send:
        await scheduler.check_assignment_reminders(db)
        
        # Verify mock_send called for student2 (pending) but not student1 (submitted)
        assert mock_send.call_count == 1
        print(f"Notifications sent: {mock_send.call_count}")
        
        args, kwargs = mock_send.call_args
        assert kwargs.get('user_id') == 2
        assert "Test Assignment 1" in kwargs.get('subject')
        assert "student_pending" in kwargs.get('body')
        
        # Verify assignment.due_reminder_sent was updated
        assert assignment.due_reminder_sent is True
        print("Assignment flag updated: True")
        
        print("Assignment reminder test passed!")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_assignment_reminder_logic())
