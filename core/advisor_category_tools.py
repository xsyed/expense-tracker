from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional, TypedDict, cast

from django.db.models import Q, QuerySet, Sum

from .models import Transaction
from .models import User as UserModel

_CATEGORY_SPENDING_SUMMARY_CAP = 20
_ACCOUNT_BALANCE_WARNING = "Accounts do not store true current balances; summaries use transactions only."


class MissingDataMetadata(TypedDict):
    accounts_lack_current_balances: bool
    warnings: list[str]


class CategorySpendingSummaryRow(TypedDict):
    category: str
    total: float
    share: float
    avg_monthly: float


def get_category_spending_summary(
    user: UserModel,
    *,
    start_date: datetime.date,
    end_date: datetime.date,
    limit: int = _CATEGORY_SPENDING_SUMMARY_CAP,
) -> dict[str, object]:
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date.")

    month_count = _month_count(start_date, end_date)
    capped_limit = min(max(limit, 1), _CATEGORY_SPENDING_SUMMARY_CAP)
    transactions = Transaction.objects.filter(
        Q(category__isnull=True) | Q(category__category_type="expense"),
        expense_month__user=user,
        transaction_type="expense",
        date__gte=start_date,
        date__lte=end_date,
    )
    total = transactions.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    rows = _category_rows(transactions, total, month_count, capped_limit)
    return {
        "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "units": {"money": "CAD"},
        "total_expenses": _money(total),
        "month_count": month_count,
        "rows": rows,
        "missing_data": _missing_data_metadata(),
    }


def _category_rows(
    transactions: QuerySet[Transaction],
    total_expenses: Decimal,
    month_count: int,
    limit: int,
) -> list[CategorySpendingSummaryRow]:
    grouped_rows = transactions.values("category__name").annotate(total=Sum("amount"))
    sorted_rows = sorted(
        grouped_rows,
        key=lambda row: (
            -cast(Decimal, row["total"] or Decimal("0")),
            (cast(Optional[str], row["category__name"]) or "Uncategorized").lower(),
        ),
    )
    return [
        _category_row(
            category=cast(Optional[str], row["category__name"]) or "Uncategorized",
            total=cast(Decimal, row["total"] or Decimal("0")),
            total_expenses=total_expenses,
            month_count=month_count,
        )
        for row in sorted_rows[:limit]
    ]


def _category_row(
    *,
    category: str,
    total: Decimal,
    total_expenses: Decimal,
    month_count: int,
) -> CategorySpendingSummaryRow:
    share = Decimal("0") if total_expenses == 0 else total / total_expenses * Decimal("100")
    return {
        "category": category,
        "total": _money(total),
        "share": float(share.quantize(Decimal("0.1"))),
        "avg_monthly": _money(total / month_count),
    }


def _money(amount: Decimal) -> float:
    return float(amount.quantize(Decimal("0.01")))


def _month_count(start_date: datetime.date, end_date: datetime.date) -> int:
    return (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1


def _missing_data_metadata() -> MissingDataMetadata:
    return {
        "accounts_lack_current_balances": True,
        "warnings": [_ACCOUNT_BALANCE_WARNING],
    }
