from __future__ import annotations

from django.http import HttpRequest
from django.urls import get_script_prefix


def script_prefix(request: HttpRequest) -> dict[str, str]:
    prefix = get_script_prefix()
    return {"SCRIPT_PREFIX": prefix.rstrip("/")}
