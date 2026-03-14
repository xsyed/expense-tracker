from __future__ import annotations

import datetime
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpRequest, JsonResponse

from .models import Transaction

_STABLE_THRESHOLD = 5.0


def _category_trend(amounts: list[float]) -> tuple[str, float | None, float]:
    if len(amounts) < 2:  # noqa: PLR2004
        return ("stable", None, 0.0)
    prior_avg = sum(amounts[:-1]) / len(amounts[:-1])
    last = amounts[-1]
    abs_change = round(last - prior_avg, 2)
    if prior_avg == 0:
        return ("up" if last > 0 else "stable", None, abs_change)
    pct = round((last - prior_avg) / prior_avg * 100, 1)
    if abs(pct) < _STABLE_THRESHOLD:
        return ("stable", pct, abs_change)
    return ("up" if pct > 0 else "down", pct, abs_change)


@login_required
def category_trends_data_view(request: HttpRequest) -> JsonResponse:
    user = request.user
    try:
        num_months = int(request.GET.get("months", "6"))
    except (ValueError, TypeError):
        num_months = 6
    if num_months not in (3, 6, 12):
        num_months = 6

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

    rows = (
        Transaction.objects.filter(
            expense_month__user=user,
            transaction_type="expense",
            expense_month__month__in=month_starts,
            category__isnull=False,
        )
        .values("category__name", "expense_month__month")
        .annotate(total=Sum("amount"))
    )

    cat_monthly: dict[str, dict[str, float]] = defaultdict(lambda: dict.fromkeys(month_keys, 0.0))
    for row in rows:
        cat_name: str = row["category__name"]
        m_key = row["expense_month__month"].strftime("%Y-%m")
        if m_key in cat_monthly[cat_name]:
            cat_monthly[cat_name][m_key] = float(row["total"] or 0)

    categories = []
    movers_data: list[tuple[str, float, float]] = []
    for name in sorted(cat_monthly):
        amounts = [round(cat_monthly[name][k], 2) for k in month_keys]
        if not any(a > 0 for a in amounts):
            continue
        direction, pct_change, abs_change = _category_trend(amounts)
        categories.append({"name": name, "amounts": amounts, "direction": direction, "pct_change": pct_change})
        if pct_change is not None:
            movers_data.append((name, pct_change, abs_change))

    movers_up = sorted([md for md in movers_data if md[1] > 0], key=lambda x: x[1], reverse=True)[:5]
    movers_down = sorted([md for md in movers_data if md[1] < 0], key=lambda x: x[1])[:5]

    return JsonResponse(
        {
            "months": month_keys,
            "categories": categories,
            "movers_up": [{"name": n, "pct_change": p, "abs_change": a} for n, p, a in movers_up],
            "movers_down": [{"name": n, "pct_change": p, "abs_change": a} for n, p, a in movers_down],
        }
    )
