
import asyncio
import sys
import os
from unittest.mock import MagicMock, patch

# Mock database and models
sys.path.append(os.path.abspath("d:/LMS-v2/backend"))

async def test_notifications():
    print("Testing send_content_added_notification...")
    
    # Mock DB session
    db = MagicMock()
    
    # Mock template
    template = MagicMock()
    template.name = "New Resource Added Notification"
    template.subject = "New Resource Added: {resource_title}"
    template.body = "Dear {username}, a new {resource_type} has been added."
    template.is_active = True
    
    # Mock student
    student = MagicMock()
    student.id = 1
    student.username = "test_student"
    student.email = "student@example.com"
    student.user_type = "Student"
    student.role = "Student"
    
    # Mock session/module/course
    session = MagicMock()
    session.id = 1
    session.title = "Test Session"
    
    module = MagicMock()
    module.title = "Test Module"
    
    course = MagicMock()
    course.title = "Test Course"
    course.id = 1
    
    # Setup DB query returns
    def mock_query(model):
        query = MagicMock()
        if "EmailTemplate" in str(model):
            query.filter.return_value.first.return_value = template
        elif "CohortCourseSession" in str(model) or "Session" in str(model):
            query.filter.return_value.first.return_value = session
        elif "CohortCourseModule" in str(model) or "Module" in str(model):
            query.filter.return_value.first.return_value = module
        elif "CohortSpecificCourse" in str(model) or "Course" in str(model):
            query.filter.return_value.first.return_value = course
        elif "User" in str(model):
            query.join.return_value.filter.return_value.all.return_value = [student]
        return query

    db.query.side_effect = mock_query
    
    from email_utils import send_content_added_notification
    
    # Test global
    print("Testing global notification...")
    with patch("notification_service.NotificationService.send_email_notification") as mock_send:
        await send_content_added_notification(
            db=db,
            session_id=1,
            content_title="Global Link",
            content_type="LINK",
            session_type="global"
        )
        mock_send.assert_called_once()
        print("Global notification test passed!")

    # Test cohort
    print("Testing cohort notification...")
    with patch("notification_service.NotificationService.send_email_notification") as mock_send:
        await send_content_added_notification(
            db=db,
            session_id=1,
            content_title="Cohort Resource",
            content_type="RESOURCE",
            session_type="cohort"
        )
        mock_send.assert_called_once()
        print("Cohort notification test passed!")

if __name__ == "__main__":
    asyncio.run(test_notifications())
