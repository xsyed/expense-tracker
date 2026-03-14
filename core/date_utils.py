from __future__ import annotations

import datetime


def parse_month_range(raw: str | None, default: int = 6) -> tuple[list[str], list[datetime.date]]:
    """Return (month_keys, month_starts) for the given number of months back from today."""
    try:
        num_months = int(raw or str(default))
    except (ValueError, TypeError):
        num_months = default
    if num_months not in (3, 6, 12):
        num_months = default

    today = datetime.date.today()
    month_keys: list[str] = []
    month_starts: list[datetime.date] = []
    y, m = today.year, today.month
    for _ in range(num_months):
        month_keys.append(f"{y:04d}-{m:02d}")
        month_starts.append(datetime.date(y, m, 1))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    month_keys.reverse()
    month_starts.reverse()
    return month_keys, month_starts
