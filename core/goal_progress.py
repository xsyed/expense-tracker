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


def _capped_goal_entries(
    entries: list[tuple[datetime.date, Decimal]],
    target_amount: Decimal,
) -> list[tuple[datetime.date, Decimal]]:
    remaining = target_amount
    capped_entries: list[tuple[datetime.date, Decimal]] = []
    for entry_date, amount in sorted(entries, key=lambda entry: entry[0]):
        if remaining <= 0:
            break
        capped_amount = min(amount, remaining)
        capped_entries.append((entry_date, capped_amount))
        remaining -= capped_amount
    return capped_entries


def savings_goal_progress_entries(goal: Goal) -> list[tuple[datetime.date, Decimal]]:
    contribution_entries = [(c.date, c.amount) for c in goal.contributions.order_by("date")]
    transaction_entries = [(t.date, t.amount) for t in savings_transfer_transactions(goal).order_by("date")]
    return _capped_goal_entries(contribution_entries + transaction_entries, goal.target_amount)


def savings_goal_progress(goal: Goal) -> Decimal:
    return sum((amount for _, amount in savings_goal_progress_entries(goal)), Decimal(0))


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
