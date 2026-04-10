from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TIMEOUT_SECONDS = 5


def verify_turnstile(token: str, remote_ip: str) -> bool:
    data = urllib.parse.urlencode(
        {
            "secret": settings.TURNSTILE_SECRET_KEY,
            "response": token,
            "remoteip": remote_ip,
        }
    ).encode()
    req = urllib.request.Request(SITEVERIFY_URL, data=data, method="POST")  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # noqa: S310
            body: dict[str, object] = json.loads(resp.read())
    except Exception:
        logger.exception("Turnstile verification request failed")
        return False
    return bool(body.get("success"))
