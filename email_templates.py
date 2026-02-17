"""
Email templates for LMS notifications
"""

def get_welcome_email_template():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: #007bff; color: white; padding: 20px; text-align: center; }
            .content { padding: 20px; background: #f9f9f9; }
            .footer { padding: 10px; text-align: center; font-size: 12px; color: #666; }
            .button { background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Welcome to Kambaa AI LMS</h1>
            </div>
            <div class="content">
                <h2>Hello {username}!</h2>
                <p>Welcome to our Learning Management System. Your account has been successfully created.</p>
                <p><strong>Your Details:</strong></p>
                <ul>
                    <li>Username: {username}</li>
                    <li>Email: {email}</li>
                    <li>Role: {role}</li>
                </ul>
                <p>You can now log in and start exploring our courses.</p>
                <a href="{login_url}" class="button">Login Now</a>
            </div>
            <div class="footer">
                <p>© 2024 Kambaa AI LMS. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

def get_course_enrollment_template():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: #28a745; color: white; padding: 20px; text-align: center; }
            .content { padding: 20px; background: #f9f9f9; }
            .footer { padding: 10px; text-align: center; font-size: 12px; color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Course Enrollment Confirmation</h1>
            </div>
            <div class="content">
                <h2>Hello {username}!</h2>
                <p>You have successfully enrolled in the course:</p>
                <h3>{course_title}</h3>
                <p>{course_description}</p>
                <p>Start your learning journey today!</p>
            </div>
            <div class="footer">
                <p>© 2024 Kambaa AI LMS. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

def get_assignment_notification_template():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: #ffc107; color: #333; padding: 20px; text-align: center; }
            .content { padding: 20px; background: #f9f9f9; }
            .footer { padding: 10px; text-align: center; font-size: 12px; color: #666; }
            .urgent { color: #dc3545; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>New Assignment</h1>
            </div>
            <div class="content">
                <h2>Hello {username}!</h2>
                <p>A new assignment has been posted:</p>
                <h3>{assignment_title}</h3>
                <p>{assignment_description}</p>
                <p class="urgent">Due Date: {due_date}</p>
                <p>Don't forget to submit your assignment on time!</p>
            </div>
            <div class="footer">
                <p>© 2024 Kambaa AI LMS. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

def get_session_reminder_template():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: #17a2b8; color: white; padding: 20px; text-align: center; }
            .content { padding: 20px; background: #f9f9f9; }
            .footer { padding: 10px; text-align: center; font-size: 12px; color: #666; }
            .button { background: #17a2b8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Session Reminder</h1>
            </div>
            <div class="content">
                <h2>Hello {username}!</h2>
                <p>Don't forget about your upcoming session:</p>
                <h3>{session_title}</h3>
                <p><strong>Course:</strong> {course_title}</p>
                <p><strong>Date & Time:</strong> {session_time}</p>
                <p><strong>Duration:</strong> {duration} minutes</p>
                {zoom_link}
            </div>
            <div class="footer">
                <p>© 2024 Kambaa AI LMS. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

def get_certificate_template():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: #6f42c1; color: white; padding: 20px; text-align: center; }
            .content { padding: 20px; background: #f9f9f9; }
            .footer { padding: 10px; text-align: center; font-size: 12px; color: #666; }
            .congratulations { color: #6f42c1; font-size: 24px; font-weight: bold; text-align: center; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎉 Congratulations!</h1>
            </div>
            <div class="content">
                <div class="congratulations">Course Completed!</div>
                <h2>Hello {username}!</h2>
                <p>Congratulations on successfully completing the course:</p>
                <h3>{course_title}</h3>
                <p>Your certificate is now available for download.</p>
                <p>Keep up the excellent work!</p>
            </div>
            <div class="footer">
                <p>© 2024 Kambaa AI LMS. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """