"""Email sending tool."""

import logging
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

SENDER_EMAIL = os.getenv("JARVIS_EMAIL", "")
SENDER_PASSWORD = os.getenv("JARVIS_EMAIL_PASSWORD", "")


def _is_valid_email(addr: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', addr))


@function_tool
async def validate_email(email: str) -> str:
    """
    Validates an email address format.

    Args:
        email: The email address to validate.
    """
    return (f"'{email}' is a valid email address."
            if _is_valid_email(email) else
            f"'{email}' is not a valid email format.")


@function_tool
async def send_email(
    to_email: str,
    subject: str,
    message: str,
    cc_email: Optional[str] = None,
) -> str:
    """
    Sends an email via authenticated Gmail SMTP.

    Args:
        to_email: Primary recipient email address.
        subject: Email subject line.
        message: Email body content.
        cc_email: Optional CC recipient email.
    """
    logger.info(f"Sending email to: {to_email}")

    if not _is_valid_email(to_email):
        return f"Invalid recipient email: {to_email}"
    if cc_email and not _is_valid_email(cc_email):
        return f"Invalid CC email: {cc_email}"
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        return ("Email credentials not configured. "
                "Please set JARVIS_EMAIL and JARVIS_EMAIL_PASSWORD in your .env file.")

    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        if cc_email:
            msg["Cc"] = cc_email
        msg.attach(MIMEText(message, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            recipients = [to_email] + ([cc_email] if cc_email else [])
            server.sendmail(SENDER_EMAIL, recipients, msg.as_string())

        return f"Email sent successfully to {to_email}."
    except Exception as e:
        return f"Failed to send email: {e}"
