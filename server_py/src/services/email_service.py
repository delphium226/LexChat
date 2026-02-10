import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..config import settings

logger = logging.getLogger("app")


def _get_transport():
    """Create SMTP connection to Gmail. Returns None if not configured."""
    if not settings.email_user or not settings.email_pass:
        return None
    return settings.email_user, settings.email_pass


async def send_welcome_email(to: str, username: str, password: str) -> None:
    """Send a welcome email to a newly created user."""
    creds = _get_transport()
    if not creds:
        logger.warning("Email credentials not configured. Skipping welcome email.")
        return

    email_user, email_pass = creds

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Welcome to LexChat UK"
    msg["From"] = email_user
    msg["To"] = to

    html = f"""
    <h3>Welcome to LexChat UK!</h3>
    <p>Your account has been created successfully.</p>
    <p><strong>Username:</strong> {username}</p>
    <p><strong>Password:</strong> {password}</p>
    <p>Please log in and change your password immediately.</p>
    <br>
    <p>Best regards,<br>The LexChat Team</p>
    """
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_user, email_pass)
            server.sendmail(email_user, to, msg.as_string())
        logger.info(f"Welcome email sent to {to}")
    except Exception as e:
        logger.error(f"Error sending welcome email: {e}")


async def send_password_reset_email(to: str, username: str, reset_token: str) -> None:
    """Send a password reset email."""
    creds = _get_transport()
    if not creds:
        logger.warning("Email credentials not configured. Skipping reset email.")
        return

    email_user, email_pass = creds

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Password Reset Request"
    msg["From"] = email_user
    msg["To"] = to

    html = f"""
    <h3>Password Reset Request</h3>
    <p>Hello {username},</p>
    <p>We received a request to reset your password.</p>
    <p>Since this is an internal mocked reset flow, please contact your administrator
    to manually reset your credentials if you cannot remember them.</p>
    <p>If you did recall your password, you can change it in the Settings page.</p>
    <br>
    <p>Best regards,<br>The LexChat Team</p>
    """
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_user, email_pass)
            server.sendmail(email_user, to, msg.as_string())
        logger.info(f"Password reset email sent to {to}")
    except Exception as e:
        logger.error(f"Error sending reset email: {e}")
