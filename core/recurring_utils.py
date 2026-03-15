from __future__ import annotations

import datetime
import re
from collections import Counter, defaultdict
from decimal import Decimal
from statistics import median

from .merchant_utils import normalize_merchant

_TRAILING_NOISE_RE = re.compile(r"[\s#\-:]*\d[\d/.\-\s]*$")
_DATE_SUFFIX_RE = re.compile(
    r"\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{2,4}$",
    re.IGNORECASE,
)
_AMOUNT_TOLERANCE = Decimal("0.2")
_MIN_PREFIX_LEN = 12
_TOO_FREQUENT_DAYS = 4
_MIN_SPAN_DAYS = 21
_CONSISTENCY_THRESHOLD = 0.6
# (name, min_gap_days, max_gap_days, annual_multiplier, min_occurrences)
_FREQ_RANGES: tuple[tuple[str, int, int, float, int], ...] = (
    ("weekly", 4, 10, 52.0, 4),
    ("monthly", 25, 35, 12.0, 3),
    ("quarterly", 75, 100, 4.0, 3),
)


def _normalize_for_recurring(desc: str) -> str:
    result = normalize_merchant(desc)
    result = _DATE_SUFFIX_RE.sub("", result)
    result = _TRAILING_NOISE_RE.sub("", result)
    return result.strip()


def _merge_prefix_groups(
    groups: dict[str, list[tuple[str, Decimal, datetime.date]]],
) -> dict[str, list[tuple[str, Decimal, datetime.date]]]:
    keys = sorted(groups, key=len, reverse=True)
    merged: dict[str, list[tuple[str, Decimal, datetime.date]]] = {}
    absorbed: set[str] = set()
    for key in keys:
        if key in absorbed:
            continue
        merged[key] = list(groups[key])
        for other in keys:
            if other in absorbed or other == key or len(other) < _MIN_PREFIX_LEN:
                continue
            if key.startswith(other) or other.startswith(key):
                target = key if len(key) >= len(other) else other
                source = other if target == key else key
                if target not in merged:
                    merged[target] = list(groups[target])
                merged[target].extend(groups[source])
                absorbed.add(source)
                if source == key:
                    break
    return merged


def _detect_frequency(dates: list[datetime.date]) -> tuple[str, float] | None:
    if len(dates) < 2:  # noqa: PLR2004
        return None
    sorted_dates = sorted(dates)
    gaps = [(sorted_dates[i + 1] - sorted_dates[i]).days for i in range(len(sorted_dates) - 1)]
    med_gap = median(gaps)
    if med_gap < _TOO_FREQUENT_DAYS:
        return None
    for freq_name, min_gap, max_gap, annual_mult, min_occ in _FREQ_RANGES:
        if len(sorted_dates) < min_occ:
            continue
        in_range = sum(1 for g in gaps if min_gap <= g <= max_gap)
        if in_range / len(gaps) >= _CONSISTENCY_THRESHOLD:
            return (freq_name, annual_mult)
    if len(sorted_dates) >= 4:  # noqa: PLR2004
        return ("other", 365.0 / float(med_gap))
    return None


def detect_recurring(
    transactions: list[tuple[str, Decimal, datetime.date]],
) -> list[dict[str, object]]:
    raw_groups: dict[str, list[tuple[str, Decimal, datetime.date]]] = defaultdict(list)
    for desc, amount, date in transactions:
        norm = _normalize_for_recurring(desc)
        if norm:
            raw_groups[norm].append((desc, amount, date))

    groups = _merge_prefix_groups(raw_groups)
    items: list[dict[str, object]] = []
    for entries in groups.values():
        amounts = [e[1] for e in entries]
        med = median(amounts)
        if med <= 0:
            continue
        filtered = [(d, a, dt) for d, a, dt in entries if abs(a - med) <= med * _AMOUNT_TOLERANCE]
        date_list = sorted({dt for _, _, dt in filtered})
        if len(date_list) < 2:  # noqa: PLR2004
            continue
        if (date_list[-1] - date_list[0]).days < _MIN_SPAN_DAYS:
            continue
        result = _detect_frequency(date_list)
        if result is None:
            continue
        frequency, annual_mult = result
        avg_amount = sum(a for _, a, _ in filtered) / len(filtered)
        desc_counts: Counter[str] = Counter(d for d, _, _ in filtered)
        items.append(
            {
                "description": desc_counts.most_common(1)[0][0],
                "avg_amount": round(float(avg_amount), 2),
                "frequency": frequency,
                "occurrences": len(date_list),
                "annual_estimate": round(float(avg_amount) * annual_mult, 2),
            }
        )

    items.sort(key=lambda x: float(str(x["annual_estimate"])), reverse=True)

    seen: set[tuple[str, float]] = set()
    deduped: list[dict[str, object]] = []
    for item in items:
        key = (str(item["description"]), float(str(item["avg_amount"])))
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped
