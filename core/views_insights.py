from __future__ import annotations

import calendar
import datetime
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from .models import CategoryBudget, ExpenseMonth, Transaction


@login_required
def insights_view(request: HttpRequest) -> HttpResponse:
    return render(request, "insights/index.html")


@login_required
def budget_data_view(request: HttpRequest) -> JsonResponse:
    user = request.user

    expense_months = ExpenseMonth.objects.filter(user=user).values_list("month", flat=True).order_by("-month")
    available_months = [m.strftime("%Y-%m") for m in expense_months]

    if not available_months:
        return JsonResponse(
            {
                "available_months": [],
                "selected_month": "",
                "categories": [],
                "totals": {"budgeted": 0.0, "spent": 0.0, "remaining": 0.0, "pct_used": 0.0},
            }
        )

    default_month = available_months[0]
    month_param = request.GET.get("month", default_month)
    if month_param not in available_months:
        month_param = default_month

    try:
        year, month = int(month_param[:4]), int(month_param[5:7])
    except (ValueError, IndexError):
        return JsonResponse({"error": "Invalid month parameter"}, status=400)

    month_start = datetime.date(year, month, 1)
    month_end = datetime.date(year + 1, 1, 1) if month == 12 else datetime.date(year, month + 1, 1)  # noqa: PLR2004

    budgets = CategoryBudget.objects.filter(user=user).select_related("category").order_by("category__name")

    if not budgets.exists():
        return JsonResponse(
            {
                "available_months": available_months,
                "selected_month": month_param,
                "categories": [],
                "totals": {"budgeted": 0.0, "spent": 0.0, "remaining": 0.0, "pct_used": 0.0},
            }
        )

    category_ids = [b.category_id for b in budgets]
    spent_rows = (
        Transaction.objects.filter(
            expense_month__user=user,
            transaction_type="expense",
            date__gte=month_start,
            date__lt=month_end,
            category_id__in=category_ids,
        )
        .values("category_id")
        .annotate(total=Sum("amount"))
    )
    spent_map: dict[int, float] = {row["category_id"]: float(row["total"] or 0) for row in spent_rows}

    category_data = []
    total_budgeted = Decimal(0)
    total_spent = Decimal(0)

    for budget in budgets:
        budgeted = float(budget.amount)
        spent = spent_map.get(budget.category_id, 0.0)
        remaining = budgeted - spent
        pct_used = (spent / budgeted * 100) if budgeted > 0 else 0.0
        category_data.append(
            {
                "name": budget.category.name,
                "budgeted": budgeted,
                "spent": round(spent, 2),
                "remaining": round(remaining, 2),
                "pct_used": round(pct_used, 1),
            }
        )
        total_budgeted += budget.amount
        total_spent += Decimal(str(spent))

    total_remaining = float(total_budgeted) - float(total_spent)
    overall_pct = (float(total_spent) / float(total_budgeted) * 100) if total_budgeted > 0 else 0.0

    return JsonResponse(
        {
            "available_months": available_months,
            "selected_month": month_param,
            "categories": category_data,
            "totals": {
                "budgeted": float(total_budgeted),
                "spent": float(total_spent),
                "remaining": round(total_remaining, 2),
                "pct_used": round(overall_pct, 1),
            },
        }
    )


def _parse_month_param(raw: str) -> tuple[int, int] | None:
    try:
        return int(raw[:4]), int(raw[5:7])
    except (ValueError, IndexError):
        return None


@login_required
def burn_rate_data_view(request: HttpRequest) -> JsonResponse:
    user = request.user
    today = datetime.date.today()
    month_param = request.GET.get("month", today.strftime("%Y-%m"))

    parsed = _parse_month_param(month_param)
    if parsed is None:
        return JsonResponse({"error": "Invalid month parameter"}, status=400)
    year, month = parsed

    budgets = CategoryBudget.objects.filter(user=user).select_related("category")
    total_budget = float(sum(b.amount for b in budgets))
    if total_budget == 0:
        return JsonResponse({"days": [], "actual": [], "ideal": [], "total_budget": 0})

    days_in_month = calendar.monthrange(year, month)[1]
    month_start = datetime.date(year, month, 1)
    month_end = datetime.date(year, month, days_in_month)

    is_current_month = year == today.year and month == today.month
    last_day = today.day if is_current_month else days_in_month

    category_ids = [b.category_id for b in budgets]
    daily_totals: dict[datetime.date, Decimal] = dict(
        Transaction.objects.filter(
            expense_month__user=user,
            transaction_type="expense",
            date__gte=month_start,
            date__lte=month_end,
            category_id__in=category_ids,
        )
        .values_list("date")
        .annotate(total=Sum("amount"))
    )

    days: list[int] = []
    actual: list[float] = []
    ideal: list[float] = []
    cumulative = 0.0
    ideal_daily = total_budget / days_in_month

    for day in range(1, last_day + 1):
        d = datetime.date(year, month, day)
        cumulative += float(daily_totals.get(d, 0))
        days.append(day)
        actual.append(round(cumulative, 2))
        ideal.append(round(ideal_daily * day, 2))

    return JsonResponse({"days": days, "actual": actual, "ideal": ideal, "total_budget": total_budget})
