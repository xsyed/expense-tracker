from __future__ import annotations

import pandas as pd
from django.contrib.auth.decorators import login_required
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from .date_utils import parse_month_range
from .models import Transaction

_SERIES_KEYS = ["income", "fixed", "variable", "savings_transfer", "savings"]


def _empty_response(month_keys: list[str], unassigned_count: int) -> JsonResponse:
    n = len(month_keys)
    return JsonResponse(
        {
            "months": month_keys,
            "unassigned_count": unassigned_count,
            "monthly": {k: [0.0] * n for k in _SERIES_KEYS},
            "averages": {k: 0.0 for k in _SERIES_KEYS},
            "savings_rate": 0.0,
            "savings_breakdown": {"explicit_transfers": 0.0, "unallocated": 0.0},
            "category_stats": [],
        }
    )


def _build_dataframe(qs: QuerySet[Transaction]) -> pd.DataFrame:
    rows = list(
        qs.values(
            "amount",
            "transaction_type",
            "category__name",
            "category__category_type",
            "category__expense_type",
            "expense_month__month",
        )
    )
    df = pd.DataFrame(rows)
    df = df.rename(
        columns={
            "category__name": "category_name",
            "category__category_type": "category_type",
            "category__expense_type": "expense_type",
            "expense_month__month": "month_date",
        }
    )
    df["expense_type"] = df["expense_type"].fillna("variable")
    df["category_name"] = df["category_name"].fillna("Uncategorized")
    df["category_type"] = df["category_type"].fillna("expense")
    df["month"] = df["month_date"].apply(lambda d: d.strftime("%Y-%m"))
    df["amount"] = df["amount"].astype(float)
    return df


def _monthly_series(df: pd.DataFrame, month_keys: list[str]) -> dict[str, pd.Series[float]]:
    is_exp = df["transaction_type"] == "expense"

    def _reindex(s: pd.Series[float]) -> pd.Series[float]:
        return s.reindex(month_keys, fill_value=0.0)

    inc = _reindex(df[df["transaction_type"] == "income"].groupby("month")["amount"].sum())
    fix = _reindex(df[is_exp & (df["expense_type"] == "fixed")].groupby("month")["amount"].sum())
    var = _reindex(df[is_exp & (df["expense_type"] == "variable")].groupby("month")["amount"].sum())
    sav_tx = _reindex(df[is_exp & (df["expense_type"] == "savings_transfer")].groupby("month")["amount"].sum())

    return {"income": inc, "fixed": fix, "variable": var, "savings_transfer": sav_tx, "savings": inc - fix - var}


def _category_stats(df: pd.DataFrame, month_keys: list[str]) -> list[dict[str, str | float]]:
    expense_df = df[df["transaction_type"] == "expense"]
    if expense_df.empty:
        return []

    cat_monthly = expense_df.groupby(["category_name", "month"])["amount"].sum()
    cat_types = expense_df.groupby("category_name")["expense_type"].first()

    stats: list[dict[str, str | float]] = []
    for name in sorted(cat_types.index):
        series = cat_monthly.loc[name].reindex(month_keys, fill_value=0.0)
        avg = float(series.mean())
        mn = float(series.min())
        mx = float(series.max())
        exp_type = str(cat_types[name])
        cut = max(0.0, avg - mn) if exp_type == "variable" else 0.0
        stats.append(
            {
                "category_name": name,
                "expense_type": exp_type,
                "avg_spend": round(avg, 2),
                "min_spend": round(mn, 2),
                "max_spend": round(mx, 2),
                "cut_potential": round(cut, 2),
            }
        )
    return stats


@login_required
def savings_planner_view(request: HttpRequest) -> HttpResponse:
    return render(request, "savings_planner/index.html")


@login_required
def savings_planner_overview_api(request: HttpRequest) -> JsonResponse:
    month_keys, month_starts = parse_month_range(request.GET.get("months"))

    base_qs = Transaction.objects.filter(
        expense_month__user=request.user,
        expense_month__month__in=month_starts,
    )
    unassigned_count = base_qs.filter(transaction_type="unassigned").count()

    qs = base_qs.exclude(transaction_type="unassigned")
    if not qs.exists():
        return _empty_response(month_keys, unassigned_count)

    df = _build_dataframe(qs)
    monthly = _monthly_series(df, month_keys)
    avgs = {k: float(v.mean()) for k, v in monthly.items()}

    avg_inc = avgs["income"]
    rate = (avg_inc - avgs["fixed"] - avgs["variable"]) / avg_inc * 100 if avg_inc > 0 else 0.0

    return JsonResponse(
        {
            "months": month_keys,
            "unassigned_count": unassigned_count,
            "monthly": {k: [round(x, 2) for x in v.tolist()] for k, v in monthly.items()},
            "averages": {k: round(v, 2) for k, v in avgs.items()},
            "savings_rate": round(rate, 2),
            "savings_breakdown": {
                "explicit_transfers": round(avgs["savings_transfer"], 2),
                "unallocated": round(avg_inc - avgs["fixed"] - avgs["variable"] - avgs["savings_transfer"], 2),
            },
            "category_stats": _category_stats(df, month_keys),
        }
    )
