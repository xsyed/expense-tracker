#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path


def send_email(subject: str, body: str, attachment: str | None = None) -> None:
    api_key = os.environ.get("RESEND_API_KEY", "")
    email_from = os.environ.get("RESEND_FROM", "")
    email_to = os.environ.get("BACKUP_EMAIL_TO", "")

    if not all([api_key, email_from, email_to]):
        print("ERROR: RESEND_API_KEY, RESEND_FROM, and BACKUP_EMAIL_TO must be set", file=sys.stderr)
        sys.exit(1)

    payload: dict[str, object] = {
        "from": email_from,
        "to": [email_to],
        "subject": subject,
        "text": body,
    }

    if attachment:
        path = Path(attachment)
        if not path.exists():
            print(f"ERROR: Attachment not found: {attachment}", file=sys.stderr)
            sys.exit(1)
        content_b64 = base64.b64encode(path.read_bytes()).decode()
        payload["attachments"] = [{"filename": path.name, "content": content_b64}]

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req):  # noqa: S310
            pass
    except urllib.error.HTTPError as e:
        print(f"ERROR: Resend API returned {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)

    print(f"Email sent: {subject}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send email via Resend API")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--attachment")
    args = parser.parse_args()
    send_email(args.subject, args.body, args.attachment)


if __name__ == "__main__":
    main()
