"""
Simple email notification helper.

Requires env vars:
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
  MAIL_FROM, MAIL_TO (comma-separated for multiple)

Usage:
  python -m scripts.notify_email "Subject" "Body text"
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import List


def send_email(subject: str, body: str) -> None:
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    mail_from = os.environ.get("MAIL_FROM")
    mail_to = os.environ.get("MAIL_TO", "")

    if not all([host, user, password, mail_from, mail_to]):
        raise RuntimeError("Missing SMTP or mail env vars.")

    recipients: List[str] = [addr.strip() for addr in mail_to.split(",") if addr.strip()]
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m scripts.notify_email \"Subject\" \"Body\"")
        raise SystemExit(1)
    send_email(sys.argv[1], sys.argv[2])
