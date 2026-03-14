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
_MIN_RECURRING_MONTHS = 3
_MIN_PREFIX_LEN = 12


def _normalize_for_recurring(desc: str) -> str:
    result = normalize_merchant(desc)
    result = _DATE_SUFFIX_RE.sub("", result)
    result = _TRAILING_NOISE_RE.sub("", result)
    return result.strip()


def _merge_prefix_groups(
    groups: dict[str, list[tuple[str, Decimal, str]]],
) -> dict[str, list[tuple[str, Decimal, str]]]:
    keys = sorted(groups, key=len, reverse=True)
    merged: dict[str, list[tuple[str, Decimal, str]]] = {}
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


def _month_span(sorted_months: list[str]) -> int:
    first, last = sorted_months[0], sorted_months[-1]
    return (int(last[:4]) - int(first[:4])) * 12 + int(last[5:7]) - int(first[5:7]) + 1


def _detect_frequency(distinct: int, span: int) -> tuple[str, float]:
    if distinct <= 1 or span <= 0:
        return ("other", float(distinct))
    avg_gap = span / (distinct - 1)
    if avg_gap <= 1.5:  # noqa: PLR2004
        return ("monthly", 12.0)
    if avg_gap <= 4.0:  # noqa: PLR2004
        return ("quarterly", 4.0)
    return ("other", 12.0 / avg_gap)


def detect_recurring(
    transactions: list[tuple[str, Decimal, datetime.date]],
) -> list[dict[str, object]]:
    raw_groups: dict[str, list[tuple[str, Decimal, str]]] = defaultdict(list)
    for desc, amount, date in transactions:
        norm = _normalize_for_recurring(desc)
        if norm:
            raw_groups[norm].append((desc, amount, date.strftime("%Y-%m")))

    groups = _merge_prefix_groups(raw_groups)
    items: list[dict[str, object]] = []
    for entries in groups.values():
        amounts = [e[1] for e in entries]
        if len(amounts) < _MIN_RECURRING_MONTHS:
            continue
        med = median(amounts)
        if med <= 0:
            continue
        filtered = [(d, a, m) for d, a, m in entries if abs(a - med) <= med * _AMOUNT_TOLERANCE]
        month_set = {m for _, _, m in filtered}
        if len(month_set) < _MIN_RECURRING_MONTHS:
            continue
        avg_amount = sum(a for _, a, _ in filtered) / len(filtered)
        sorted_m = sorted(month_set)
        frequency, annual_mult = _detect_frequency(len(month_set), _month_span(sorted_m))
        desc_counts: Counter[str] = Counter(d for d, _, _ in filtered)
        items.append(
            {
                "description": desc_counts.most_common(1)[0][0],
                "avg_amount": round(float(avg_amount), 2),
                "frequency": frequency,
                "months_detected": len(month_set),
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
