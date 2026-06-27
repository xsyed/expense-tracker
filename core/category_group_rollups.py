from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, TypedDict, cast

from django.db.models import Sum

from .models import ExpenseMonth, Transaction
from .models import User as UserModel

UNGROUPED_GROUP_NAME = "Ungrouped"
UNCATEGORIZED_CATEGORY_NAME = "Uncategorized"


class CategoryGroupCategoryRow(TypedDict):
    category_id: int | None
    category_name: str
    spent: float


class CategoryGroupSpendRow(TypedDict):
    group_id: int | None
    group_name: str
    spent: float
    categories: list[CategoryGroupCategoryRow]


@dataclass
class _CategoryAccumulator:
    category_id: int | None
    category_name: str
    spent: Decimal = Decimal("0")


@dataclass
class _GroupAccumulator:
    group_id: int | None
    group_name: str
    spent: Decimal = Decimal("0")
    categories: dict[tuple[int | None, str], _CategoryAccumulator] = field(default_factory=dict)


def _round_money(amount: Decimal) -> float:
    return float(amount.quantize(Decimal("0.01")))


def build_expense_group_rollups(
    user: UserModel,
    *,
    expense_month: ExpenseMonth | None = None,
    month_start: datetime.date | None = None,
    month_end: datetime.date | None = None,
) -> list[CategoryGroupSpendRow]:
    transactions = Transaction.objects.filter(expense_month__user=user, transaction_type="expense")
    if expense_month is not None:
        transactions = transactions.filter(expense_month=expense_month)
    elif month_start is not None and month_end is not None:
        transactions = transactions.filter(date__gte=month_start, date__lt=month_end)
    else:
        raise ValueError("Provide either expense_month or month_start/month_end")

    rows = (
        transactions.values(
            "category_id",
            "category__name",
            "category__category_type",
            "category__category_group_id",
            "category__category_group__name",
        )
        .annotate(total=Sum("amount"))
        .order_by()
    )

    groups: dict[int | None, _GroupAccumulator] = {}
    for row in rows:
        spent = cast(Decimal, row["total"] or Decimal("0"))
        if spent == 0:
            continue

        is_expense_category = row["category__category_type"] == "expense"
        group_id = cast(Optional[int], row["category__category_group_id"] if is_expense_category else None)
        group_name = cast(Optional[str], row["category__category_group__name"] if is_expense_category else None)
        category_id = cast(Optional[int], row["category_id"] if is_expense_category else None)
        category_name = cast(Optional[str], row["category__name"] if is_expense_category else None)

        group = groups.setdefault(
            group_id,
            _GroupAccumulator(
                group_id=group_id,
                group_name=group_name or UNGROUPED_GROUP_NAME,
            ),
        )
        group.spent += spent

        category_key = (category_id, category_name or UNCATEGORIZED_CATEGORY_NAME)
        category = group.categories.setdefault(
            category_key,
            _CategoryAccumulator(
                category_id=category_id,
                category_name=category_name or UNCATEGORIZED_CATEGORY_NAME,
            ),
        )
        category.spent += spent

    result: list[CategoryGroupSpendRow] = []
    for group in groups.values():
        categories = sorted(group.categories.values(), key=lambda item: (-item.spent, item.category_name.lower()))
        result.append(
            {
                "group_id": group.group_id,
                "group_name": group.group_name,
                "spent": _round_money(group.spent),
                "categories": [
                    {
                        "category_id": category.category_id,
                        "category_name": category.category_name,
                        "spent": _round_money(category.spent),
                    }
                    for category in categories
                ],
            }
        )

    return sorted(result, key=lambda group: (-group["spent"], group["group_name"].lower()))
