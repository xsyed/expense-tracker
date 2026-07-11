from __future__ import annotations

import calendar
import datetime
from decimal import Decimal
from typing import Literal, Optional, TypedDict, cast

from django.db.models import QuerySet, Sum
from django.utils import timezone

from .category_group_rollups import build_expense_group_rollups
from .goal_progress import (
    debt_goal_progress,
    savings_goal_progress,
    savings_transfer_transactions,
    spending_goal_progress,
)
from .models import AdvisorMemory, CategoryBudget, Goal, Transaction
from .models import User as UserModel
from .recurring_utils import build_category_breakdown, detect_recurring

DatePreset = Literal["last_7_days", "this_month", "previous_month"]
Trend = Literal["improving", "declining", "stable", "insufficient_data"]
Confidence = Literal["low", "medium", "high"]

_CATEGORY_CAP = 12
_EVIDENCE_CAP = 10
_GOAL_CAP = 20
_RECURRING_CAP = 20
_NEAR_LIMIT_PCT = 80.0
_ACCOUNT_BALANCE_WARNING = "Accounts do not store true current balances; summaries use transactions only."


class MissingDataMetadata(TypedDict):
    accounts_lack_current_balances: bool
    warnings: list[str]


class SpendingCategoryRow(TypedDict):
    category: str
    amount: float


class EvidenceRow(TypedDict):
    date: str
    merchant: str
    amount: float
    category: str
    account: str


class BudgetCategoryRow(TypedDict):
    category: str
    budget: float
    spent: float
    remaining: float
    pct_used: float


class CashFlowMonthRow(TypedDict):
    month: str
    income: float
    fixed_expenses: float
    variable_expenses: float
    savings_transfers: float
    net_cash_flow: float


class RecurringItem(TypedDict):
    description: str
    frequency: str
    average_amount: float
    monthly_estimate: float
    annual_estimate: float
    occurrences: int
    confidence: Confidence


class GoalStatusRow(TypedDict):
    id: int
    name: str
    goal_type: str
    target: float
    progress: float
    deadline: str | None
    gap: float
    required_monthly_amount: float | None
    current_pace: float
    pct_complete: float
    is_completed: bool


def _money(amount: Decimal) -> float:
    return float(amount.quantize(Decimal("0.01")))


def _date_range_payload(start_date: datetime.date, end_date: datetime.date) -> dict[str, str]:
    return {"start": start_date.isoformat(), "end": end_date.isoformat()}


def _missing_data_metadata() -> MissingDataMetadata:
    return {
        "accounts_lack_current_balances": True,
        "warnings": [_ACCOUNT_BALANCE_WARNING],
    }


def _month_end(month_start: datetime.date) -> datetime.date:
    days = calendar.monthrange(month_start.year, month_start.month)[1]
    return datetime.date(month_start.year, month_start.month, days)


def _next_month_start(month_start: datetime.date) -> datetime.date:
    if month_start.month == 12:  # noqa: PLR2004
        return datetime.date(month_start.year + 1, 1, 1)
    return datetime.date(month_start.year, month_start.month + 1, 1)


def _normalize_month(month: datetime.date) -> datetime.date:
    return datetime.date(month.year, month.month, 1)


def _preset_range(preset: DatePreset, today: datetime.date) -> tuple[datetime.date, datetime.date]:
    if preset == "last_7_days":
        return today - datetime.timedelta(days=6), today
    if preset == "this_month":
        return today.replace(day=1), today
    first_this_month = today.replace(day=1)
    previous_end = first_this_month - datetime.timedelta(days=1)
    return previous_end.replace(day=1), previous_end


def _transaction_base(user: UserModel) -> QuerySet[Transaction]:
    return Transaction.objects.filter(expense_month__user=user)


def _spending_transactions(
    user: UserModel,
    start_date: datetime.date,
    end_date: datetime.date,
) -> QuerySet[Transaction]:
    return (
        _transaction_base(user)
        .filter(transaction_type="expense", date__gte=start_date, date__lte=end_date)
        .select_related("category", "account")
    )


def _evidence_rows(transactions: QuerySet[Transaction], limit: int) -> list[EvidenceRow]:
    rows: list[EvidenceRow] = []
    for transaction in transactions.order_by("-amount", "-date")[:limit]:
        rows.append(
            {
                "date": transaction.date.isoformat(),
                "merchant": transaction.description,
                "amount": _money(transaction.amount),
                "category": transaction.category.name if transaction.category else "Uncategorized",
                "account": transaction.account.name if transaction.account else "Unspecified",
            }
        )
    return rows


def _category_spending_rows(transactions: QuerySet[Transaction], limit: int) -> list[SpendingCategoryRow]:
    rows = (
        transactions.values("category__name").annotate(total=Sum("amount")).order_by("-total", "category__name")[:limit]
    )
    return [
        {
            "category": cast(Optional[str], row["category__name"]) or "Uncategorized",
            "amount": _money(cast(Decimal, row["total"] or Decimal("0"))),
        }
        for row in rows
    ]


def get_user_profile_memory(user: UserModel) -> dict[str, object]:
    memory = AdvisorMemory.objects.filter(user=user).first()
    if memory is None:
        return {"content": "", "updated_at": None}
    return {"content": memory.content, "updated_at": memory.updated_at.isoformat()}


def get_recent_spending_brief(
    user: UserModel,
    *,
    preset: DatePreset | None = None,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    include_evidence: bool = False,
    evidence_limit: int = _EVIDENCE_CAP,
) -> dict[str, object]:
    today = timezone.localdate()
    if preset is not None:
        start_date, end_date = _preset_range(preset, today)
    if start_date is None or end_date is None:
        raise ValueError("Provide either a preset or both start_date and end_date.")
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date.")

    transactions = _spending_transactions(user, start_date, end_date)
    total = transactions.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    result: dict[str, object] = {
        "date_range": _date_range_payload(start_date, end_date),
        "preset": preset,
        "units": {"money": "CAD"},
        "total_spent": _money(total),
        "transaction_count": transactions.count(),
        "top_categories": _category_spending_rows(transactions, _CATEGORY_CAP),
        "missing_data": _missing_data_metadata(),
    }
    if include_evidence:
        result["evidence"] = _evidence_rows(transactions, min(evidence_limit, _EVIDENCE_CAP))
    return result


def _budget_category_rows(user: UserModel, month_start: datetime.date) -> list[BudgetCategoryRow]:
    month_end_exclusive = _next_month_start(month_start)
    budgets = CategoryBudget.objects.filter(user=user, category__category_type="expense").select_related("category")
    spent_rows = (
        Transaction.objects.filter(
            expense_month__user=user,
            transaction_type="expense",
            date__gte=month_start,
            date__lt=month_end_exclusive,
            category__category_type="expense",
        )
        .values("category_id")
        .annotate(total=Sum("amount"))
    )
    spent_by_category = {row["category_id"]: cast(Decimal, row["total"] or Decimal("0")) for row in spent_rows}
    rows: list[BudgetCategoryRow] = []
    for budget in budgets:
        spent = spent_by_category.get(budget.category_id, Decimal("0"))
        remaining = budget.amount - spent
        pct_used = spent / budget.amount * Decimal("100") if budget.amount > 0 else Decimal("0")
        rows.append(
            {
                "category": budget.category.name,
                "budget": _money(budget.amount),
                "spent": _money(spent),
                "remaining": _money(remaining),
                "pct_used": float(pct_used.quantize(Decimal("0.1"))),
            }
        )
    return sorted(rows, key=lambda row: (-row["spent"], row["category"].lower()))


def get_budget_position(user: UserModel, *, month: datetime.date) -> dict[str, object]:
    month_start = _normalize_month(month)
    rows = _budget_category_rows(user, month_start)
    total_budget = sum((Decimal(str(row["budget"])) for row in rows), Decimal("0"))
    total_spent = sum((Decimal(str(row["spent"])) for row in rows), Decimal("0"))
    over_budget = [row for row in rows if row["remaining"] < 0][:_CATEGORY_CAP]
    near_limit = [row for row in rows if row["remaining"] >= 0 and row["pct_used"] >= _NEAR_LIMIT_PCT][:_CATEGORY_CAP]
    return {
        "month": month_start.strftime("%Y-%m"),
        "units": {"money": "CAD"},
        "totals": {
            "budget": _money(total_budget),
            "spent": _money(total_spent),
            "remaining": _money(total_budget - total_spent),
        },
        "over_budget_categories": over_budget,
        "near_limit_categories": near_limit,
        "category_group_rollups": build_expense_group_rollups(
            user,
            month_start=month_start,
            month_end=_next_month_start(month_start),
        ),
        "missing_data": _missing_data_metadata(),
    }


def _monthly_cash_flow(user: UserModel, months: list[datetime.date]) -> list[CashFlowMonthRow]:
    rows: list[CashFlowMonthRow] = []
    for month_start in months:
        month_end_exclusive = _next_month_start(month_start)
        transactions = _transaction_base(user).filter(date__gte=month_start, date__lt=month_end_exclusive)
        income = transactions.filter(transaction_type="income").aggregate(total=Sum("amount"))["total"] or Decimal("0")
        fixed = _expense_type_total(transactions, "fixed")
        savings = _expense_type_total(transactions, "savings_transfer")
        expense_total = transactions.filter(transaction_type="expense").aggregate(total=Sum("amount"))[
            "total"
        ] or Decimal("0")
        variable = expense_total - fixed - savings
        rows.append(
            {
                "month": month_start.strftime("%Y-%m"),
                "income": _money(income),
                "fixed_expenses": _money(fixed),
                "variable_expenses": _money(variable),
                "savings_transfers": _money(savings),
                "net_cash_flow": _money(income - fixed - variable - savings),
            }
        )
    return rows


def _expense_type_total(transactions: QuerySet[Transaction], expense_type: str) -> Decimal:
    return transactions.filter(
        transaction_type="expense",
        category__category_type="expense",
        category__expense_type=expense_type,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")


def _cash_flow_trend(rows: list[CashFlowMonthRow]) -> Trend:
    if len(rows) < 3:  # noqa: PLR2004
        return "insufficient_data"
    split = len(rows) // 2
    early = rows[:split]
    recent = rows[split:]
    early_avg = sum((Decimal(str(row["net_cash_flow"])) for row in early), Decimal("0")) / len(early)
    recent_avg = sum((Decimal(str(row["net_cash_flow"])) for row in recent), Decimal("0")) / len(recent)
    delta = recent_avg - early_avg
    if abs(delta) < Decimal("25"):
        return "stable"
    return "improving" if delta > 0 else "declining"


def get_cash_flow_summary(
    user: UserModel,
    *,
    months: int = 6,
    end_month: datetime.date | None = None,
) -> dict[str, object]:
    capped_months = min(max(months, 1), 12)
    latest_month = _normalize_month(end_month or timezone.localdate())
    month_starts = []
    current = latest_month
    for _ in range(capped_months):
        month_starts.append(current)
        current = (
            datetime.date(current.year - 1, 12, 1)
            if current.month == 1
            else datetime.date(current.year, current.month - 1, 1)
        )
    month_starts.reverse()
    rows = _monthly_cash_flow(user, month_starts)
    average = sum((Decimal(str(row["net_cash_flow"])) for row in rows), Decimal("0")) / len(rows)
    return {
        "date_range": _date_range_payload(month_starts[0], _month_end(month_starts[-1])),
        "units": {"money": "CAD"},
        "months": rows,
        "average_net_cash_flow": _money(average),
        "trend": _cash_flow_trend(rows),
        "missing_data": _missing_data_metadata(),
    }


def _recurring_confidence(occurrences: int, frequency: str) -> Confidence:
    if occurrences >= 5:  # noqa: PLR2004
        return "high"
    if occurrences >= 3 or frequency in {"monthly", "quarterly"}:  # noqa: PLR2004
        return "medium"
    return "low"


def get_recurring_obligations(user: UserModel, *, limit: int = _RECURRING_CAP) -> dict[str, object]:
    transactions_with_cats: list[tuple[str, Decimal, datetime.date, str | None]] = list(
        Transaction.objects.filter(expense_month__user=user, transaction_type="expense").values_list(
            "description",
            "amount",
            "date",
            "category__name",
        )
    )
    recurring = detect_recurring(
        [(desc, amount, date) for desc, amount, date, _category in transactions_with_cats],
        as_of=timezone.localdate(),
    )
    items: list[RecurringItem] = []
    for item in recurring[: min(limit, _RECURRING_CAP)]:
        annual = Decimal(str(item["annual_estimate"]))
        occurrences = int(cast(int, item["occurrences"]))
        frequency = str(item["frequency"])
        items.append(
            {
                "description": str(item["description"]),
                "frequency": frequency,
                "average_amount": float(cast(float, item["avg_amount"])),
                "monthly_estimate": _money(annual / Decimal("12")),
                "annual_estimate": _money(annual),
                "occurrences": occurrences,
                "confidence": _recurring_confidence(occurrences, frequency),
            }
        )
    total_annual = sum((Decimal(str(item["annual_estimate"])) for item in items), Decimal("0"))
    return {
        "items": items,
        "summary": {
            "estimated_monthly_total": _money(total_annual / Decimal("12")),
            "estimated_annual_total": _money(total_annual),
            "confidence": _recurring_confidence(max((item["occurrences"] for item in items), default=0), "other"),
        },
        "category_breakdown": build_category_breakdown(transactions_with_cats, recurring),
        "missing_data": _missing_data_metadata(),
    }


def _goal_progress(goal: Goal, today: datetime.date) -> Decimal:
    if goal.goal_type == "savings":
        return savings_goal_progress(goal)
    if goal.goal_type == "debt":
        return debt_goal_progress(goal)
    return spending_goal_progress(goal, today.replace(day=1))


def _goal_activity_start(goal: Goal) -> datetime.date:
    if goal.goal_type == "savings":
        first_contribution = goal.contributions.order_by("date").values_list("date", flat=True).first()
        first_transaction = savings_transfer_transactions(goal).order_by("date").values_list("date", flat=True).first()
        savings_dates = [date for date in [first_contribution, first_transaction] if date is not None]
        first = min(savings_dates) if savings_dates else None
    elif goal.goal_type == "debt" and goal.category_id is not None:
        first = (
            Transaction.objects.filter(
                expense_month__user=goal.user,
                category_id=goal.category_id,
                transaction_type="expense",
            )
            .order_by("date")
            .values_list("date", flat=True)
            .first()
        )
    else:
        first = None
    return first or timezone.localtime(goal.created_at).date()


def _goal_current_pace(goal: Goal, progress: Decimal, today: datetime.date) -> Decimal:
    if goal.goal_type == "spending":
        days_in_month = Decimal(str(calendar.monthrange(today.year, today.month)[1]))
        return progress / Decimal(str(today.day)) * days_in_month if today.day > 0 else Decimal("0")
    start_date = _goal_activity_start(goal)
    active_months = max(Decimal("1"), Decimal(str((today - start_date).days)) / Decimal("30"))
    return progress / active_months


def _required_monthly_amount(goal: Goal, gap: Decimal, today: datetime.date) -> float | None:
    if goal.deadline is None:
        return None
    months_remaining = Decimal(str((goal.deadline - today).days)) / Decimal("30")
    if months_remaining <= 0:
        return _money(gap) if gap > 0 else 0.0
    return _money(gap / months_remaining) if gap > 0 else 0.0


def _goal_status_row(goal: Goal, today: datetime.date) -> GoalStatusRow:
    progress = _goal_progress(goal, today)
    gap = goal.target_amount - progress
    pct_complete = progress / goal.target_amount * Decimal("100") if goal.target_amount > 0 else Decimal("0")
    return {
        "id": goal.id,
        "name": goal.name,
        "goal_type": goal.goal_type,
        "target": _money(goal.target_amount),
        "progress": _money(progress),
        "deadline": goal.deadline.isoformat() if goal.deadline else None,
        "gap": _money(gap),
        "required_monthly_amount": _required_monthly_amount(goal, gap, today),
        "current_pace": _money(_goal_current_pace(goal, progress, today)),
        "pct_complete": float(min(pct_complete, Decimal("100")).quantize(Decimal("0.1"))),
        "is_completed": progress >= goal.target_amount,
    }


def get_goal_status(
    user: UserModel,
    *,
    goal_id: int | None = None,
    today: datetime.date | None = None,
) -> dict[str, object]:
    effective_today = today or timezone.localdate()
    goals = Goal.objects.filter(user=user).select_related("category").prefetch_related("contributions")
    selected_goal = goals.filter(pk=goal_id).first() if goal_id is not None else None
    goal_rows = [_goal_status_row(goal, effective_today) for goal in goals.order_by("-created_at")[:_GOAL_CAP]]
    return {
        "as_of": effective_today.isoformat(),
        "units": {"money": "CAD"},
        "goals": goal_rows,
        "selected_goal": _goal_status_row(selected_goal, effective_today) if selected_goal is not None else None,
        "count": len(goal_rows),
        "capped": len(goal_rows) == _GOAL_CAP,
        "missing_data": _missing_data_metadata(),
    }
