from __future__ import annotations

import datetime
from decimal import Decimal

from django.db.models import Sum
from django.db.models.query import QuerySet
from django.utils import timezone

from .models import Goal, Transaction


def _sum_amount(transactions: QuerySet[Transaction]) -> Decimal:
    return transactions.aggregate(total=Sum("amount"))["total"] or Decimal(0)


def savings_transfer_transactions(goal: Goal) -> QuerySet[Transaction]:
    if goal.category_id is None:
        return Transaction.objects.none()
    return Transaction.objects.filter(
        expense_month__user=goal.user,
        category_id=goal.category_id,
        transaction_type="expense",
        date__gte=timezone.localtime(goal.created_at).date(),
    )


def savings_goal_progress(goal: Goal) -> Decimal:
    contribution_total = goal.contributions.aggregate(total=Sum("amount"))["total"] or Decimal(0)
    return contribution_total + _sum_amount(savings_transfer_transactions(goal))


def spending_goal_progress(goal: Goal, month_start: datetime.date) -> Decimal:
    if goal.category_id is None:
        return Decimal(0)
    return _sum_amount(
        Transaction.objects.filter(
            expense_month__user=goal.user,
            expense_month__month=month_start,
            category_id=goal.category_id,
            transaction_type="expense",
        )
    )


def debt_payment_transactions(goal: Goal) -> QuerySet[Transaction]:
    if goal.category_id is None:
        return Transaction.objects.none()
    return Transaction.objects.filter(
        expense_month__user=goal.user,
        category_id=goal.category_id,
        transaction_type="expense",
        date__gte=timezone.localtime(goal.created_at).date(),
    )


def debt_goal_progress(goal: Goal) -> Decimal:
    return _sum_amount(debt_payment_transactions(goal))
