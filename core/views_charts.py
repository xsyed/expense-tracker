from __future__ import annotations

import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.http import HttpRequest, JsonResponse

from .models import Transaction
from .views_months import _cutoff_date


@login_required
def chart_monthly_totals_view(request: HttpRequest) -> JsonResponse:
    months_param = request.GET.get("months", "6")
    base_qs = Transaction.objects.filter(
        expense_month__user=request.user,
        transaction_type__in=["income", "expense"],
    )
    if months_param != "all":
        try:
            months = int(months_param)
        except (ValueError, TypeError):
            months = 6
        base_qs = base_qs.filter(date__gte=_cutoff_date(months))

    rows = (
        base_qs.annotate(month=TruncMonth("date"))
        .values("month", "transaction_type")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )

    pivot = {}
    for row in rows:
        m = row["month"]
        if m is None:
            continue
        key = m.strftime("%Y-%m")
        if key not in pivot:
            pivot[key] = {"income": 0.0, "expense": 0.0}
        pivot[key][row["transaction_type"]] = float(row["total"] or 0)

    sorted_keys = sorted(pivot.keys())
    labels, income, expense = [], [], []
    for key in sorted_keys:
        year, month = int(key[:4]), int(key[5:7])
        labels.append(datetime.date(year, month, 1).strftime("%b %Y"))
        income.append(pivot[key]["income"])
        expense.append(pivot[key]["expense"])

    return JsonResponse({"labels": labels, "income": income, "expense": expense})


@login_required
def chart_category_breakdown_view(request: HttpRequest) -> JsonResponse:
    month_param = request.GET.get("month", "")

    months_qs = (
        Transaction.objects.filter(expense_month__user=request.user, transaction_type="expense")
        .annotate(month=TruncMonth("date"))
        .values_list("month", flat=True)
        .distinct()
        .order_by("-month")
    )
    available_months = [m.strftime("%Y-%m") for m in months_qs if m is not None]

    if not available_months:
        return JsonResponse({"labels": [], "series": [], "available_months": []})

    if not month_param or month_param not in available_months:
        month_param = available_months[0]

    try:
        year, month = int(month_param[:4]), int(month_param[5:7])
    except (ValueError, IndexError):
        return JsonResponse({"labels": [], "series": [], "available_months": available_months})

    month_start = datetime.date(year, month, 1)
    month_end = datetime.date(year + 1, 1, 1) if month == 12 else datetime.date(year, month + 1, 1)  # noqa: PLR2004

    rows = (
        Transaction.objects.filter(
            expense_month__user=request.user,
            transaction_type="expense",
            date__gte=month_start,
            date__lt=month_end,
        )
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    labels, series = [], []
    for row in rows:
        labels.append(row["category__name"] or "Unclassified")
        series.append(float(row["total"] or 0))

    return JsonResponse({"labels": labels, "series": series, "available_months": available_months})


@login_required
def chart_top_categories_view(request: HttpRequest) -> JsonResponse:
    months_param = request.GET.get("months", "6")
    try:
        limit = max(1, int(request.GET.get("limit", "5")))
    except (ValueError, TypeError):
        limit = 5

    base_qs = Transaction.objects.filter(
        expense_month__user=request.user,
        transaction_type="expense",
        category__isnull=False,
    )
    if months_param != "all":
        try:
            months = int(months_param)
        except (ValueError, TypeError):
            months = 6
        base_qs = base_qs.filter(date__gte=_cutoff_date(months))

    rows = base_qs.values("category__name").annotate(total=Sum("amount")).order_by("-total")[:limit]

    labels = [row["category__name"] for row in rows]
    totals = [float(row["total"] or 0) for row in rows]
    overall = sum(totals)
    percentages = [round((t / overall) * 100, 1) if overall > 0 else 0.0 for t in totals]

    return JsonResponse({"labels": labels, "totals": totals, "percentages": percentages})


@login_required
def chart_month_over_month_view(request: HttpRequest) -> JsonResponse:
    months_qs = (
        Transaction.objects.filter(expense_month__user=request.user, transaction_type="expense")
        .annotate(month=TruncMonth("date"))
        .values_list("month", flat=True)
        .distinct()
        .order_by("-month")[:2]
    )
    recent_months = sorted([m for m in months_qs if m is not None])

    if len(recent_months) < 2:  # noqa: PLR2004
        return JsonResponse({"insufficient": True})

    all_categories: set[str] = set()
    month_data: dict[datetime.date, dict[str, float]] = {}
    for m in recent_months:
        next_month = datetime.date(m.year + 1, 1, 1) if m.month == 12 else datetime.date(m.year, m.month + 1, 1)  # noqa: PLR2004

        rows = (
            Transaction.objects.filter(
                expense_month__user=request.user,
                transaction_type="expense",
                date__gte=m,
                date__lt=next_month,
            )
            .values("category__name")
            .annotate(total=Sum("amount"))
        )
        month_data[m] = {}
        for row in rows:
            cat = row["category__name"] or "Unclassified"
            month_data[m][cat] = float(row["total"] or 0)
            all_categories.add(cat)

    month_labels = [m.strftime("%b %Y") for m in recent_months]
    series = [
        {"name": cat, "data": [month_data[m].get(cat, 0) for m in recent_months]} for cat in sorted(all_categories)
    ]

    return JsonResponse({"months": month_labels, "series": series})
