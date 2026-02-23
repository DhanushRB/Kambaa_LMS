
import asyncio
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock

# Add backend to path
sys.path.append(os.path.abspath("d:/LMS-v2/backend"))

async def test_feedback_notification():
    print("Testing send_feedback_submission_confirmation...")
    
    # Mock DB session
    db = MagicMock()
    
    # Mock template
    template = MagicMock()
    template.name = "Feedback Submission Confirmation"
    template.subject = "Thank You for Your Feedback: {feedback_title}"
    template.body = "Dear {username}, thank you for your feedback on {feedback_title} in {session_title}. Submitted on {submitted_at}."
    template.is_active = True
    
    # Mock student
    student = MagicMock()
    student.id = 1
    student.username = "test_student"
    student.email = "student@example.com"
    
    # Mock session
    session = MagicMock()
    session.id = 1
    session.title = "Test Session"
    
    # Setup DB query returns
    def mock_query(model):
        query = MagicMock()
        if "EmailTemplate" in str(model):
            query.filter.return_value.first.return_value = template
        elif "User" in str(model):
            query.filter.return_value.first.return_value = student
        elif "Session" in str(model):
            query.filter.return_value.first.return_value = session
        return query

    db.query.side_effect = mock_query
    
    from email_utils import send_feedback_submission_confirmation
    
    print("Testing feedback confirmation email...")
    with patch("notification_service.NotificationService.send_email_notification") as mock_send:
        await send_feedback_submission_confirmation(
            db=db,
            student_id=1,
            feedback_title="Course Feedback",
            session_id=1,
            session_type="global"
        )
        
        # Verify mock_send call
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        
        print(f"Notification sent to: {kwargs.get('email')}")
        print(f"Subject: {kwargs.get('subject')}")
        print(f"Body: {kwargs.get('body')}")
        
        assert kwargs.get('user_id') == 1
        assert "Thank You for Your Feedback: Course Feedback" in kwargs.get('subject')
        assert "test_student" in kwargs.get('body')
        assert "Course Feedback" in kwargs.get('body')
        assert "Test Session" in kwargs.get('body')
        
        print("Feedback confirmation test passed!")

async def test_feedback_request():
    print("\nTesting send_feedback_request_to_students...")
    
    # Mock DB session
    db = MagicMock()
    
    # Mock template
    template = MagicMock()
    template.name = "Feedback Request Notification"
    template.subject = "New Feedback Form: {feedback_title}"
    template.body = "Dear {username}, a new feedback form {feedback_title} is available for {session_title}."
    template.is_active = True
    
    # Mock students
    students = [
        MagicMock(id=10, username="student1", email="s1@ex.com"),
        MagicMock(id=11, username="student2", email="s2@ex.com")
    ]
    
    # Mock session/module/course
    session = MagicMock(id=1, title="Global Session")
    module = MagicMock(id=1, course_id=1)
    
    # Setup DB query returns
    def mock_query(model):
        query = MagicMock()
        if "EmailTemplate" in str(model):
            query.filter.return_value.first.return_value = template
        elif "User" in str(model):
            # Join/filter chain for target_students
            query.join.return_value.filter.return_value.all.return_value = students
        elif "Session" in str(model):
            query.filter.return_value.first.return_value = session
        elif "Module" in str(model):
            query.filter.return_value.first.return_value = module
        return query

    db.query.side_effect = mock_query
    
    from email_utils import send_feedback_request_to_students
    
    with patch("notification_service.NotificationService.send_email_notification") as mock_send:
        await send_feedback_request_to_students(
            db=db,
            feedback_title="Quarterly Review",
            session_id=1,
            session_type="global"
        )
        
        # Verify mock_send called twice (for 2 students)
        assert mock_send.call_count == 2
        print(f"Notifications sent: {mock_send.call_count}")
        
        # Check first call content
        args, kwargs = mock_send.call_args_list[0]
        assert "New Feedback Form: Quarterly Review" in kwargs.get('subject')
        assert "Quarterly Review" in kwargs.get('body')
        assert "Global Session" in kwargs.get('body')
        
        print("Feedback request test passed!")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_feedback_notification())
    loop.run_until_complete(test_feedback_request())
