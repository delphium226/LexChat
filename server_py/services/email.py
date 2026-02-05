import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import settings
import logging

logger = logging.getLogger("lexchat.email")

def send_email(to_email: str, subject: str, html_content: str):
    if not settings.EMAIL_USER or not settings.EMAIL_PASS:
        logger.warning("Email credentials not configured. Skipping email send.")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = settings.EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(html_content, 'html'))

        # Assuming Gmail for now as per Node.js legacy config
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(settings.EMAIL_USER, settings.EMAIL_PASS)
        text = msg.as_string()
        server.sendmail(settings.EMAIL_USER, to_email, text)
        server.quit()
        logger.info(f"Email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

def send_welcome_email(to_email: str, username: str, password: str):
    subject = "Welcome to LexChat UK"
    html_content = f"""
        <h3>Welcome to LexChat UK!</h3>
        <p>Your account has been created successfully.</p>
        <p><strong>Username:</strong> {username}</p>
        <p><strong>Password:</strong> {password}</p>
        <p>Please log in and change your password immediately.</p>
        <br>
        <p>Best regards,<br>The LexChat Team</p>
    """
    send_email(to_email, subject, html_content)

def send_password_reset_email(to_email: str, username: str, reset_token: str):
    # In a real app, this would be a link to a frontend route with the token
    subject = "Password Reset Request"
    html_content = f"""
        <h3>Password Reset Request</h3>
        <p>Hello {username},</p>
        <p>We received a request to reset your password.</p>
        <p>Since this is an internal mocked reset flow, please contact your administrator to manually reset your credentials if you cannot remember them.</p>
        <p>If you did recall your password, you can change it in the Settings page.</p>
        <br>
        <p>Best regards,<br>The LexChat Team</p>
    """
    send_email(to_email, subject, html_content)
