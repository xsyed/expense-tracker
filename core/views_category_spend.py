from __future__ import annotations

import datetime
from typing import cast

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from .models import CategoryBudget, Transaction
from .models import User as UserModel


@login_required
def category_spend_page_view(request: HttpRequest) -> HttpResponse:
    return render(request, "category_spend.html")


@login_required
def category_spend_data_view(request: HttpRequest) -> JsonResponse:
    user = cast(UserModel, request.user)

    months_qs = (
        Transaction.objects.filter(
            expense_month__user=user,
            transaction_type__in=["income", "expense"],
        )
        .annotate(month=TruncMonth("date"))
        .values_list("month", flat=True)
        .distinct()
        .order_by("-month")
    )
    available_months = [m.strftime("%Y-%m") for m in months_qs if m is not None]

    if not available_months:
        return JsonResponse(
            {
                "available_months": [],
                "expenses": [],
                "income": [],
                "total_expenses": 0.0,
                "total_income": 0.0,
                "net": 0.0,
            }
        )

    month_param = request.GET.get("month", "")
    if not month_param or month_param not in available_months:
        month_param = available_months[0]

    try:
        year, month = int(month_param[:4]), int(month_param[5:7])
    except (ValueError, IndexError):
        month_param = available_months[0]
        year, month = int(month_param[:4]), int(month_param[5:7])

    month_start = datetime.date(year, month, 1)
    month_end = datetime.date(year + 1, 1, 1) if month == 12 else datetime.date(year, month + 1, 1)  # noqa: PLR2004

    expense_rows = (
        Transaction.objects.filter(
            expense_month__user=user,
            transaction_type="expense",
            date__gte=month_start,
            date__lt=month_end,
        )
        .values("category_id", "category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    income_rows = (
        Transaction.objects.filter(
            expense_month__user=user,
            transaction_type="income",
            date__gte=month_start,
            date__lt=month_end,
        )
        .values("category_id", "category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    budgets = CategoryBudget.objects.filter(user=user)
    budget_map: dict[int, float] = {b.category_id: float(b.amount) for b in budgets}

    expenses = []
    total_expenses = 0.0
    for row in expense_rows:
        total = round(float(row["total"] or 0), 2)
        if total == 0:
            continue
        total_expenses += total
        category_id = row["category_id"]
        category_name = row["category__name"] or "Unclassified"
        over_budget = category_id is not None and category_id in budget_map and total > budget_map[category_id]
        expenses.append({"category": category_name, "total": total, "over_budget": over_budget})
    total_expenses = round(total_expenses, 2)

    income = []
    total_income = 0.0
    for row in income_rows:
        total = round(float(row["total"] or 0), 2)
        if total == 0:
            continue
        total_income += total
        category_name = row["category__name"] or "Unclassified"
        income.append({"category": category_name, "total": total})
    total_income = round(total_income, 2)

    net = round(total_income - total_expenses, 2)

    return JsonResponse(
        {
            "available_months": available_months,
            "expenses": expenses,
            "income": income,
            "total_expenses": total_expenses,
            "total_income": total_income,
            "net": net,
        }
    )
