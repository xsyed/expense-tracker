from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import HttpRequest, JsonResponse

from .date_utils import parse_month_range
from .models import Account, Transaction


@login_required
def accounts_overview_data_view(request: HttpRequest) -> JsonResponse:
    user = request.user
    month_keys, month_starts = parse_month_range(request.GET.get("months"))

    accounts = list(Account.objects.filter(user=user).values_list("id", "name", "account_type", "credit_limit"))

    if not accounts:
        return JsonResponse({"months": month_keys, "accounts": []})

    account_ids = [a[0] for a in accounts]
    account_names = {a[0]: a[1] for a in accounts}
    account_types = {a[0]: a[2] for a in accounts}
    account_limits: dict[int, float | None] = {a[0]: float(a[3]) if a[3] is not None else None for a in accounts}

    rows = (
        Transaction.objects.filter(
            expense_month__user=user,
            expense_month__month__in=month_starts,
            account_id__in=account_ids,
        )
        .filter(Q(transaction_type="income") | Q(transaction_type="expense"))
        .values("account_id", "transaction_type", "expense_month__month")
        .annotate(total=Sum("amount"))
    )

    # account_id -> month_key -> {income, expense}
    acc_monthly: dict[int, dict[str, dict[str, float]]] = {}
    for aid in account_ids:
        acc_monthly[aid] = {mk: {"income": 0.0, "expense": 0.0} for mk in month_keys}

    for row in rows:
        aid = row["account_id"]
        m_key = row["expense_month__month"].strftime("%Y-%m")
        tx_type = row["transaction_type"]
        if m_key in acc_monthly[aid]:
            acc_monthly[aid][m_key][tx_type] = float(row["total"] or 0)

    result: list[dict[str, object]] = []
    for aid in account_ids:
        monthly = acc_monthly[aid]
        total_income = round(sum(monthly[mk]["income"] for mk in month_keys), 2)
        total_expense = round(sum(monthly[mk]["expense"] for mk in month_keys), 2)
        is_credit_card = account_types[aid] == "credit_card"
        net = round(total_expense - total_income, 2) if is_credit_card else round(total_income - total_expense, 2)
        monthly_income = [round(monthly[mk]["income"], 2) for mk in month_keys]
        monthly_expense = [round(monthly[mk]["expense"], 2) for mk in month_keys]
        result.append(
            {
                "name": account_names[aid],
                "account_type": account_types[aid],
                "credit_limit": account_limits[aid],
                "total_income": total_income,
                "total_expense": total_expense,
                "net": net,
                "monthly_income": monthly_income,
                "monthly_expense": monthly_expense,
            }
        )

    return JsonResponse({"months": month_keys, "accounts": result})
