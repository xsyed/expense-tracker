from __future__ import annotations

import math
from typing import Any

from django import template

register = template.Library()


@register.filter
def floor(value: Any) -> int | Any:
    try:
        return math.floor(float(value))
    except (TypeError, ValueError):
        return value
