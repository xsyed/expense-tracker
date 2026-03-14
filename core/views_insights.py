from __future__ import annotations

import calendar
import datetime
import re
from collections import Counter, defaultdict
from decimal import Decimal
from statistics import median
from typing import Any, cast

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from .models import CategoryBudget, ExpenseMonth, Goal, GoalContribution, Transaction
from .models import User as UserModel

# Max months to project forward for savings goals
_MAX_PROJECTION_MONTHS = 120


@login_required
def insights_view(request: HttpRequest) -> HttpResponse:
    return render(request, "insights/index.html")


@login_required
def budget_data_view(request: HttpRequest) -> JsonResponse:
    user = cast(UserModel, request.user)
    total_budget = float(user.monthly_budget) if user.monthly_budget is not None else None

    expense_months = ExpenseMonth.objects.filter(user=user).values_list("month", flat=True).order_by("-month")
    available_months = [m.strftime("%Y-%m") for m in expense_months]

    if not available_months:
        return JsonResponse(
            {
                "available_months": [],
                "selected_month": "",
                "categories": [],
                "totals": {"budgeted": 0.0, "spent": 0.0, "remaining": 0.0, "pct_used": 0.0},
                "total_budget": total_budget,
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
                "total_budget": total_budget,
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
            "total_budget": total_budget,
        }
    )


def _savings_health_from_pace(
    target_amount: Decimal,
    progress: Decimal,
    today: datetime.date,
    months_remaining: Decimal,
    contributions: list[GoalContribution],
) -> str:
    earliest_date = min(c.date for c in contributions)
    months_active = max(Decimal("1"), Decimal(str((today - earliest_date).days)) / Decimal("30"))
    avg_monthly = progress / months_active
    pace_needed = (target_amount - progress) / months_remaining
    if avg_monthly >= pace_needed * Decimal("1.2"):
        return "ahead"
    return "on_track" if avg_monthly >= pace_needed else "behind"


def _compute_goal_health(
    goal: Goal, progress: Decimal, today: datetime.date, contributions: list[GoalContribution]
) -> str:
    if goal.goal_type == "spending":
        return "on_track" if progress <= goal.target_amount else "over"
    if progress >= goal.target_amount:
        return "completed"
    if not goal.deadline:
        return "on_track" if contributions else "behind"
    months_remaining = Decimal(str((goal.deadline - today).days)) / Decimal("30")
    if months_remaining <= 0 or not contributions:
        return "behind"
    return _savings_health_from_pace(goal.target_amount, progress, today, months_remaining, contributions)


def _build_contribution_timeline(savings_goals: list[tuple[Goal, list[GoalContribution]]]) -> dict[str, Any]:
    if not savings_goals:
        return {"months": [], "series": []}
    all_months: set[str] = set()
    per_goal_monthly: list[tuple[str, dict[str, float]]] = []
    for goal, contributions in savings_goals:
        monthly: dict[str, float] = {}
        for c in contributions:
            key = c.date.strftime("%Y-%m")
            monthly[key] = monthly.get(key, 0.0) + float(c.amount)
            all_months.add(key)
        per_goal_monthly.append((goal.name, monthly))
    if not all_months:
        return {"months": [], "series": []}
    sorted_months = sorted(all_months)
    series = []
    for name, monthly in per_goal_monthly:
        data = [round(monthly.get(m, 0.0), 2) for m in sorted_months]
        if any(v > 0 for v in data):
            series.append({"name": name, "data": data})
    return {"months": sorted_months, "series": series}


@login_required
def goals_data_view(request: HttpRequest) -> JsonResponse:
    user = request.user
    today = datetime.date.today()
    current_month_start = today.replace(day=1)
    goals = list(Goal.objects.filter(user=user).prefetch_related("contributions").select_related("category"))
    spending_category_ids = [g.category_id for g in goals if g.goal_type == "spending" and g.category_id]
    spending_map: dict[int, Decimal] = {}
    if spending_category_ids:
        rows = (
            Transaction.objects.filter(
                expense_month__user=user,
                expense_month__month=current_month_start,
                category_id__in=spending_category_ids,
                transaction_type="expense",
            )
            .values("category_id")
            .annotate(total=Sum("amount"))
        )
        spending_map = {row["category_id"]: row["total"] or Decimal(0) for row in rows}
    goal_list = []
    savings_goals: list[tuple[Goal, list[GoalContribution]]] = []
    for goal in goals:
        contributions = list(goal.contributions.all())
        if goal.goal_type == "savings":
            progress = sum((c.amount for c in contributions), Decimal(0))
            savings_goals.append((goal, contributions))
        else:
            progress = spending_map.get(goal.category_id, Decimal(0)) if goal.category_id else Decimal(0)
        pct = min(int(progress / goal.target_amount * 100), 100) if goal.target_amount > 0 else 0  # noqa: PLR2004
        health = _compute_goal_health(goal, progress, today, contributions)
        days_remaining = (goal.deadline - today).days if goal.deadline else None
        goal_list.append(
            {
                "id": goal.pk,
                "name": goal.name,
                "goal_type": goal.goal_type,
                "target_amount": float(goal.target_amount),
                "progress_amount": float(progress),
                "pct_complete": pct,
                "health": health,
                "deadline": goal.deadline.isoformat() if goal.deadline else None,
                "days_remaining": days_remaining,
            }
        )
    return JsonResponse({"goals": goal_list, "timeline": _build_contribution_timeline(savings_goals)})


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


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)  # noqa: PLR2004


@login_required
def goal_projection_data_view(request: HttpRequest, pk: int) -> JsonResponse:
    goal = Goal.objects.filter(pk=pk, user=request.user, goal_type="savings").first()
    if goal is None:
        return JsonResponse({"error": "Goal not found"}, status=404)

    contributions = list(goal.contributions.order_by("date"))
    target = float(goal.target_amount)

    # Build monthly cumulative
    monthly_totals: dict[str, float] = {}
    for c in contributions:
        key = c.date.strftime("%Y-%m")
        monthly_totals[key] = monthly_totals.get(key, 0.0) + float(c.amount)

    if not monthly_totals:
        return JsonResponse(
            {
                "goal_name": goal.name,
                "target_amount": target,
                "deadline": goal.deadline.isoformat() if goal.deadline else None,
                "historical": [],
                "projected": [],
                "estimated_completion": None,
            }
        )

    sorted_months = sorted(monthly_totals.keys())
    historical: list[dict[str, Any]] = []
    cumulative = 0.0
    for m in sorted_months:
        cumulative += monthly_totals[m]
        historical.append({"month": m, "cumulative": round(cumulative, 2)})

    # Average monthly contribution
    avg_monthly = cumulative / len(sorted_months)

    # Project forward
    projected: list[dict[str, Any]] = []
    estimated_completion: str | None = None
    if cumulative < target and avg_monthly > 0:
        last_month = sorted_months[-1]
        proj_year, proj_month = int(last_month[:4]), int(last_month[5:7])
        proj_cumulative = cumulative
        for _ in range(_MAX_PROJECTION_MONTHS):
            proj_year, proj_month = _next_month(proj_year, proj_month)
            proj_cumulative += avg_monthly
            month_key = f"{proj_year:04d}-{proj_month:02d}"
            projected.append({"month": month_key, "cumulative": round(min(proj_cumulative, target), 2)})
            if proj_cumulative >= target:
                estimated_completion = month_key
                break

    return JsonResponse(
        {
            "goal_name": goal.name,
            "target_amount": target,
            "deadline": goal.deadline.isoformat() if goal.deadline else None,
            "historical": historical,
            "projected": projected,
            "estimated_completion": estimated_completion,
        }
    )


@login_required
def spending_trend_data_view(request: HttpRequest, pk: int) -> JsonResponse:
    goal = Goal.objects.filter(pk=pk, user=request.user, goal_type="spending").select_related("category").first()
    if goal is None:
        return JsonResponse({"error": "Goal not found"}, status=404)

    target = float(goal.target_amount)
    today = datetime.date.today()

    # Build last 6 months
    months: list[str] = []
    month_starts: list[datetime.date] = []
    y, m = today.year, today.month
    for _ in range(6):
        months.append(f"{y:04d}-{m:02d}")
        month_starts.append(datetime.date(y, m, 1))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()
    month_starts.reverse()

    spending: list[float] = [0.0] * 6
    if goal.category_id is not None:
        rows = (
            Transaction.objects.filter(
                expense_month__user=request.user,
                expense_month__month__in=month_starts,
                category_id=goal.category_id,
                transaction_type="expense",
            )
            .values("expense_month__month")
            .annotate(total=Sum("amount"))
        )
        month_map: dict[str, float] = {}
        for row in rows:
            key = row["expense_month__month"].strftime("%Y-%m")
            month_map[key] = float(row["total"] or 0)
        spending = [round(month_map.get(m, 0.0), 2) for m in months]

    return JsonResponse(
        {
            "goal_name": goal.name,
            "target_amount": target,
            "category_name": goal.category.name if goal.category else "",
            "months": months,
            "spending": spending,
        }
    )


_TRAILING_NOISE_RE = re.compile(r"[\s#\-:]*\d[\d/.\-\s]*$")
_DATE_SUFFIX_RE = re.compile(
    r"\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{2,4}$",
    re.IGNORECASE,
)
_AMOUNT_TOLERANCE = Decimal("0.2")
_MIN_RECURRING_MONTHS = 3


def _normalize_description(desc: str) -> str:
    result = desc.lower().strip()
    result = _DATE_SUFFIX_RE.sub("", result)
    result = _TRAILING_NOISE_RE.sub("", result)
    return result.strip()


def _month_span(sorted_months: list[str]) -> int:
    first, last = sorted_months[0], sorted_months[-1]
    return (int(last[:4]) - int(first[:4])) * 12 + int(last[5:7]) - int(first[5:7]) + 1


def _detect_frequency(distinct: int, span: int) -> tuple[str, float]:
    if distinct <= 1 or span <= 0:
        return ("other", float(distinct))
    avg_gap = span / (distinct - 1)
    if avg_gap <= 1.5:  # noqa: PLR2004
        return ("monthly", 12.0)
    if avg_gap <= 4.0:  # noqa: PLR2004
        return ("quarterly", 4.0)
    return ("other", 12.0 / avg_gap)


def _detect_recurring(
    transactions: list[tuple[str, Decimal, datetime.date]],
) -> list[dict[str, object]]:
    groups: dict[str, list[tuple[str, Decimal, str]]] = defaultdict(list)
    for desc, amount, date in transactions:
        norm = _normalize_description(desc)
        if norm:
            groups[norm].append((desc, amount, date.strftime("%Y-%m")))

    items: list[dict[str, object]] = []
    for entries in groups.values():
        amounts = [e[1] for e in entries]
        if len(amounts) < _MIN_RECURRING_MONTHS:
            continue
        med = median(amounts)
        if med <= 0:
            continue
        filtered = [(d, a, m) for d, a, m in entries if abs(a - med) <= med * _AMOUNT_TOLERANCE]
        month_set = {m for _, _, m in filtered}
        if len(month_set) < _MIN_RECURRING_MONTHS:
            continue
        avg_amount = sum(a for _, a, _ in filtered) / len(filtered)
        sorted_m = sorted(month_set)
        frequency, annual_mult = _detect_frequency(len(month_set), _month_span(sorted_m))
        desc_counts: Counter[str] = Counter(d for d, _, _ in filtered)
        items.append(
            {
                "description": desc_counts.most_common(1)[0][0],
                "avg_amount": round(float(avg_amount), 2),
                "frequency": frequency,
                "months_detected": len(month_set),
                "annual_estimate": round(float(avg_amount) * annual_mult, 2),
            }
        )

    items.sort(key=lambda x: float(str(x["annual_estimate"])), reverse=True)
    return items


@login_required
def recurring_data_view(request: HttpRequest) -> JsonResponse:
    transactions = list(
        Transaction.objects.filter(
            expense_month__user=request.user,
            transaction_type="expense",
        ).values_list("description", "amount", "date")
    )
    items = _detect_recurring(transactions)
    total_monthly = sum(float(str(i["avg_amount"])) for i in items if i["frequency"] == "monthly")
    total_annual = sum(float(str(i["annual_estimate"])) for i in items)
    return JsonResponse(
        {
            "items": items,
            "summary": {
                "total_monthly_recurring": round(total_monthly, 2),
                "total_annual_recurring": round(total_annual, 2),
            },
        }
    )
