from __future__ import annotations

from decimal import Decimal
from typing import Literal, TypedDict

from django.db.models import Sum

from .models import Category, CategoryBudget, ExpenseMonth

BudgetStatus = Literal["over", "near", "on_track", "unbudgeted"]


class MonthBudgetRow(TypedDict):
    category_id: int
    category_name: str
    spent: float
    budget: float | None
    remaining: float | None
    progress_percent: float
    status: BudgetStatus
    status_label: str


def _status_for(spent: Decimal, budget: Decimal | None) -> BudgetStatus:
    if budget is None:
        return "unbudgeted"
    if spent > budget:
        return "over"
    if budget > 0 and spent >= budget * Decimal("0.8"):
        return "near"
    return "on_track"


def _status_label(status: BudgetStatus) -> str:
    labels: dict[BudgetStatus, str] = {
        "over": "Over",
        "near": "Near",
        "on_track": "On track",
        "unbudgeted": "Unbudgeted",
    }
    return labels[status]


def build_month_budget_rows(month: ExpenseMonth) -> list[MonthBudgetRow]:
    categories = Category.objects.filter(user=month.user, category_type="expense").order_by("name")
    budgets = CategoryBudget.objects.filter(user=month.user, category__category_type="expense")
    budget_map = {budget.category_id: budget.amount for budget in budgets}
    spent_rows = (
        month.transactions.filter(transaction_type="expense", category__category_type="expense")
        .values("category_id")
        .annotate(total=Sum("amount"))
    )
    spent_map = {row["category_id"]: row["total"] or Decimal("0") for row in spent_rows}

    rows: list[MonthBudgetRow] = []
    for category in categories:
        spent = spent_map.get(category.id, Decimal("0"))
        budget = budget_map.get(category.id)
        remaining = budget - spent if budget is not None else None
        progress_percent = float(min((spent / budget * 100), Decimal("100"))) if budget and budget > 0 else 0.0
        status = _status_for(spent, budget)
        rows.append(
            {
                "category_id": category.id,
                "category_name": category.name,
                "spent": float(spent),
                "budget": float(budget) if budget is not None else None,
                "remaining": float(remaining) if remaining is not None else None,
                "progress_percent": round(progress_percent, 1),
                "status": status,
                "status_label": _status_label(status),
            }
        )

    return sorted(rows, key=lambda row: (-row["spent"], row["category_name"].lower()))
