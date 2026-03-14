from __future__ import annotations

import datetime
from collections import defaultdict
from statistics import pstdev
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpRequest, JsonResponse

from .date_utils import parse_month_range
from .models import Transaction

_WMA_WEIGHTS = [1, 2, 3]
_TREND_THRESHOLD = 5.0
_CV_HIGH = 0.2
_CV_MEDIUM = 0.5
_MIN_CONFIDENT_MONTHS = 3


def _weighted_moving_avg(values: list[float]) -> float:
    n = min(len(values), len(_WMA_WEIGHTS))
    recent = values[-n:]
    weights = _WMA_WEIGHTS[-n:]
    return sum(v * w for v, w in zip(recent, weights)) / sum(weights)


def _confidence_level(monthly_amounts: list[float]) -> str:
    non_zero = sum(1 for v in monthly_amounts if v > 0)
    if non_zero < _MIN_CONFIDENT_MONTHS:
        return "low"
    recent = monthly_amounts[-3:]
    mean = sum(recent) / len(recent)
    if mean == 0:
        return "high"
    cv = pstdev(recent) / mean
    if cv < _CV_HIGH:
        return "high"
    return "medium" if cv < _CV_MEDIUM else "low"


def _trend_direction(avg_3m: float, avg_6m: float) -> str:
    if avg_6m == 0:
        return "up" if avg_3m > 0 else "stable"
    pct = (avg_3m - avg_6m) / avg_6m * 100
    if abs(pct) < _TREND_THRESHOLD:
        return "stable"
    return "up" if pct > 0 else "down"


def _fetch_category_series(
    user_id: int,
    month_starts: list[datetime.date],
    month_keys: list[str],
) -> dict[str, list[float]]:
    rows = (
        Transaction.objects.filter(
            expense_month__user_id=user_id,
            transaction_type="expense",
            expense_month__month__in=month_starts,
            category__isnull=False,
        )
        .values("category__name", "expense_month__month")
        .annotate(total=Sum("amount"))
    )
    raw: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        cat_name: str = row["category__name"]
        m_key = row["expense_month__month"].strftime("%Y-%m")
        raw[cat_name][m_key] = float(row["total"] or 0)
    return {name: [raw[name].get(mk, 0.0) for mk in month_keys] for name in raw}


def _build_category_forecasts(cat_series: dict[str, list[float]]) -> list[dict[str, Any]]:
    categories: list[dict[str, Any]] = []
    for name in sorted(cat_series):
        amounts = cat_series[name]
        predicted = round(_weighted_moving_avg(amounts), 2) if any(a > 0 for a in amounts) else 0.0
        avg_3m = round(sum(amounts[-3:]) / 3, 2)
        avg_6m = round(sum(amounts[-6:]) / 6, 2)
        categories.append(
            {
                "name": name,
                "predicted": predicted,
                "avg_3m": avg_3m,
                "avg_6m": avg_6m,
                "trend": _trend_direction(avg_3m, avg_6m),
                "confidence": _confidence_level(amounts),
            }
        )
    categories.sort(key=lambda c: c["predicted"], reverse=True)
    return categories


def _compute_accuracy(
    cat_series: dict[str, list[float]],
    month_keys: list[str],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for i in range(3, len(month_keys)):
        prior_has_data = any(amounts[j] > 0 for amounts in cat_series.values() for j in range(i - 3, i))
        if not prior_has_data:
            continue
        predicted = 0.0
        actual = 0.0
        for amounts in cat_series.values():
            prior = amounts[i - 3 : i]
            if any(p > 0 for p in prior):
                predicted += _weighted_moving_avg(prior)
            actual += amounts[i]
        if actual > 0:
            accuracy = max(0.0, 100.0 - abs(predicted - actual) / actual * 100)
        elif predicted == 0:
            accuracy = 100.0
        else:
            accuracy = 0.0
        entries.append(
            {
                "month": month_keys[i],
                "predicted": round(predicted, 2),
                "actual": round(actual, 2),
                "accuracy_pct": round(accuracy, 1),
            }
        )
    return entries


@login_required
def forecasting_data_view(request: HttpRequest) -> JsonResponse:
    user = request.user
    month_keys, month_starts = parse_month_range("12")
    cat_series = _fetch_category_series(user.pk, month_starts, month_keys)

    if not cat_series:
        return JsonResponse(
            {
                "prediction": None,
                "categories": [],
                "accuracy": {"entries": [], "has_data": False, "message": "No transaction history yet."},
            }
        )

    categories = _build_category_forecasts(cat_series)
    predicted_total = sum(c["predicted"] for c in categories)
    last_month_total = sum(amounts[-1] for amounts in cat_series.values())

    monthly_totals = [sum(amounts[i] for amounts in cat_series.values()) for i in range(len(month_keys))]
    overall_confidence = _confidence_level(monthly_totals)

    delta_amount = predicted_total - last_month_total
    delta_pct = (delta_amount / last_month_total * 100) if last_month_total > 0 else 0.0

    accuracy_entries = _compute_accuracy(cat_series, month_keys)
    has_accuracy = any(e["actual"] > 0 for e in accuracy_entries)
    accuracy_msg = "" if has_accuracy else "At least 4 months of history are needed to show forecast accuracy."

    return JsonResponse(
        {
            "prediction": {
                "predicted_total": round(predicted_total, 2),
                "confidence": overall_confidence,
                "last_month_total": round(last_month_total, 2),
                "delta_amount": round(delta_amount, 2),
                "delta_pct": round(delta_pct, 1),
            },
            "categories": categories,
            "accuracy": {"entries": accuracy_entries, "has_data": has_accuracy, "message": accuracy_msg},
        }
    )
