#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import smtplib
import sys
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def send_email(subject: str, body: str, attachment: str | None = None) -> None:
    gmail_address = os.environ.get("GMAIL_ADDRESS", "")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    email_to = os.environ.get("BACKUP_EMAIL_TO", "")

    if not all([gmail_address, gmail_password, email_to]):
        print("ERROR: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, and BACKUP_EMAIL_TO must be set", file=sys.stderr)
        sys.exit(1)

    msg = MIMEMultipart()
    msg["From"] = gmail_address
    msg["To"] = email_to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    if attachment:
        path = Path(attachment)
        if not path.exists():
            print(f"ERROR: Attachment not found: {attachment}", file=sys.stderr)
            sys.exit(1)
        with open(path, "rb") as f:
            part = MIMEApplication(f.read(), Name=path.name)
        part["Content-Disposition"] = f'attachment; filename="{path.name}"'
        msg.attach(part)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_address, gmail_password)
        server.sendmail(gmail_address, [email_to], msg.as_string())

    print(f"Email sent: {subject}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send email via Gmail SMTP")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--attachment")
    args = parser.parse_args()
    send_email(args.subject, args.body, args.attachment)


if __name__ == "__main__":
    main()
