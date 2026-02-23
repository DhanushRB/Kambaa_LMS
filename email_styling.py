import logging

logger = logging.getLogger(__name__)

# HTML Base Layout for Professional Emails
BASE_HTML_LAYOUT = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{subject}}</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.5; color: #333; margin: 0; padding: 0; background-color: #f4f7f9; }
        .container { max-width: 600px; margin: 10px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .header { background-color: #ffffff; padding: 15px; text-align: center; border-bottom: 3px solid #f59e0b; }
        .header img { max-height: 50px; width: auto; }
        .header h1 { margin: 5px 0 0 0; font-size: 18px; font-weight: 700; color: #1e293b; }
        .content { padding: 20px; }
        .content p { margin-bottom: 15px; font-size: 15px; }
        .details-box { background-color: #1e40af; padding: 20px; margin: 15px 0; border-radius: 6px; color: #ffffff; font-weight: bold; }
        .details-box strong { color: #ffffff; }
        .footer { background-color: #f1f5f9; padding: 15px; text-align: center; color: #64748b; font-size: 12px; border-top: 1px solid #e2e8f0; }
        .button { display: inline-block; padding: 12px 24px; background-color: #f59e0b; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 5px; }
        .divider { height: 1px; background-color: #e2e8f0; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://lms.kambaaincorporation.in/kambaa-logo.png" alt="Kambaa Logo">
            <h1>Kambaa LMS</h1>
        </div>
        <div class="content">
            {{body_content}}
        </div>
        <div class="footer">
            <p>&copy; 2026 Kambaa LMS. All rights reserved.</p>
            <p>This is an automated message. Please do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
""".strip()

def wrap_in_base_layout(body_content: str, subject: str = "Notification"):
    """
    Wraps content in the Kambaa professional HTML layout.
    Detects if the content is already a full HTML document.
    """
    # If it's already a full HTML document, return as is
    if body_content.strip().startswith('<!DOCTYPE html>') or body_content.strip().startswith('<html>'):
        return body_content
    
    # Otherwise, convert newlines to <br> and wrap
    # Strip whitespace to avoid overspacing at start/end
    html_body = body_content.strip().replace('\n', '<br>')
    
    return BASE_HTML_LAYOUT.replace("{{subject}}", subject).replace("{{body_content}}", html_body)
