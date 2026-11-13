"""Small SMTP adapter used for password recovery and support requests."""
from email.message import EmailMessage
import os
import smtplib
from urllib.parse import quote


def _send(recipient: str, subject: str, body: str) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    if not host or not sender:
        raise RuntimeError("Email delivery is not configured. Set SMTP_HOST and SMTP_FROM.")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    timeout = 12
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=timeout) as smtp:
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
        return
    with smtplib.SMTP(host, port, timeout=timeout) as smtp:
        smtp.ehlo()
        if os.getenv("SMTP_STARTTLS", "true").lower() in {"1", "true", "yes"}:
            smtp.starttls()
            smtp.ehlo()
        if username:
            smtp.login(username, password)
        smtp.send_message(message)


def send_password_reset(recipient: str, token: str) -> None:
    base_url = os.getenv("APP_BASE_URL", "http://localhost:5173").strip().rstrip("/")
    link = f"{base_url}/reset-password?token={quote(token)}"
    _send(recipient, "Reset your VoiceShield password",
          f"A password reset was requested for your VoiceShield account.\n\n"
          f"Use this one-time link within 30 minutes:\n{link}\n\n"
          "If you did not request this change, ignore this message.")


def send_support_message(sender_name: str, sender_email: str, message_text: str) -> None:
    recipient = os.getenv("SUPPORT_EMAIL", "").strip()
    if not recipient:
        raise RuntimeError("Support email is not configured. Set SUPPORT_EMAIL.")
    _send(recipient, f"VoiceShield support request from {sender_name}",
          f"From: {sender_name} <{sender_email}>\n\n{message_text}")
