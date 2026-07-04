from __future__ import annotations

import datetime
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Literal, TypedDict, cast

from django.core.cache import cache
from django.utils import timezone

Confidence = Literal["low", "medium", "high"]
Recommendation = Literal["affordable", "not_affordable", "uncertain"]
Period = Literal["monthly", "paycheck"]

_FRANKFURTER_BASE_URL = "https://api.frankfurter.app/latest"
_FRANKFURTER_CACHE_SECONDS = 60 * 60 * 12
_FRANKFURTER_TIMEOUT_SECONDS = 5


class MissingFact(TypedDict):
    name: str
    reason: str
    impact: str


def _money(amount: Decimal) -> float:
    return float(amount.quantize(Decimal("0.01")))


def _missing_fact(name: str, reason: str, impact: str) -> MissingFact:
    return {"name": name, "reason": reason, "impact": impact}


def _months_between(start_date: datetime.date, end_date: datetime.date) -> Decimal:
    days = (end_date - start_date).days
    if days <= 0:
        return Decimal("0")
    return Decimal(str(days)) / Decimal("30")


def _completion_date(today: datetime.date, gap: Decimal, period_amount: Decimal, period: Period) -> str | None:
    if gap <= 0:
        return today.isoformat()
    if period_amount <= 0:
        return None
    periods_needed = math.ceil(gap / period_amount)
    days_per_period = 30 if period == "monthly" else 14
    return (today + datetime.timedelta(days=periods_needed * days_per_period)).isoformat()


def run_affordability_check(
    *,
    amount: Decimal,
    expected_monthly_surplus: Decimal | None,
    current_available_cash: Decimal | None = None,
    minimum_reserve: Decimal | None = None,
    monthly_payment: Decimal = Decimal("0"),
    required_upfront_cash: Decimal | None = None,
) -> dict[str, object]:
    required_cash = required_upfront_cash if required_upfront_cash is not None else amount
    missing_facts: list[MissingFact] = []
    if current_available_cash is None:
        missing_facts.append(
            _missing_fact(
                "current_available_cash",
                "Available cash can materially change whether the upfront cost preserves reserves.",
                "Recommendation cannot be high confidence without current cash.",
            )
        )
    if minimum_reserve is None:
        missing_facts.append(
            _missing_fact(
                "minimum_reserve",
                "Reserve target is needed to measure the cash buffer after the decision.",
                "Reserve impact is unknown.",
            )
        )
    if expected_monthly_surplus is None:
        missing_facts.append(
            _missing_fact(
                "expected_monthly_surplus",
                "Monthly surplus is needed to assess ongoing affordability.",
                "Ongoing payment pressure is unknown.",
            )
        )

    reserve_impact = None
    cash_is_enough = None
    if current_available_cash is not None and minimum_reserve is not None:
        reserve_impact = current_available_cash - required_cash - minimum_reserve
        cash_is_enough = reserve_impact >= 0

    surplus_after_payment = None
    payment_is_affordable = None
    if expected_monthly_surplus is not None:
        surplus_after_payment = expected_monthly_surplus - monthly_payment
        payment_is_affordable = surplus_after_payment >= 0

    if cash_is_enough is False or payment_is_affordable is False:
        recommendation: Recommendation = "not_affordable"
    elif cash_is_enough is True and payment_is_affordable is True:
        recommendation = "affordable"
    else:
        recommendation = "uncertain"

    confidence: Confidence = "high" if not missing_facts else "low"
    return {
        "recommendation": recommendation,
        "required_cash": _money(required_cash),
        "expected_monthly_surplus": _money(expected_monthly_surplus) if expected_monthly_surplus is not None else None,
        "surplus_after_payment": _money(surplus_after_payment) if surplus_after_payment is not None else None,
        "reserve_impact": _money(reserve_impact) if reserve_impact is not None else None,
        "confidence": confidence,
        "missing_facts": missing_facts,
    }


def run_emergency_fund_calculation(
    *,
    monthly_essential_expenses: Decimal,
    required_months: Decimal,
    current_emergency_savings: Decimal | None = None,
    savings_amount_per_period: Decimal | None = None,
    savings_period: Period = "monthly",
    today: datetime.date | None = None,
) -> dict[str, object]:
    effective_today = today or timezone.localdate()
    target_fund = monthly_essential_expenses * required_months
    missing_facts: list[MissingFact] = []
    if current_emergency_savings is None:
        missing_facts.append(
            _missing_fact(
                "current_emergency_savings",
                "Current emergency savings is needed to calculate the remaining gap.",
                "Gap and completion date are unknown.",
            )
        )
    if savings_amount_per_period is None:
        missing_facts.append(
            _missing_fact(
                "savings_amount_per_period",
                "Savings cadence is needed to estimate completion.",
                "Estimated completion date is unknown.",
            )
        )

    gap = None if current_emergency_savings is None else max(target_fund - current_emergency_savings, Decimal("0"))
    completion_date = (
        _completion_date(effective_today, gap, savings_amount_per_period, savings_period)
        if gap is not None and savings_amount_per_period is not None
        else None
    )
    return {
        "required_months": float(required_months),
        "current_emergency_savings": _money(current_emergency_savings)
        if current_emergency_savings is not None
        else None,
        "target_fund": _money(target_fund),
        "gap": _money(gap) if gap is not None else None,
        "savings_amount_per_period": _money(savings_amount_per_period)
        if savings_amount_per_period is not None
        else None,
        "savings_period": savings_period,
        "estimated_completion_date": completion_date,
        "missing_facts": missing_facts,
    }


def run_large_event_plan(
    *,
    target_amount: Decimal,
    deadline: datetime.date | None,
    current_saved_amount: Decimal | None = None,
    planned_savings_per_month: Decimal | None = None,
    paychecks_per_month: Decimal = Decimal("2"),
    today: datetime.date | None = None,
) -> dict[str, object]:
    effective_today = today or timezone.localdate()
    missing_facts: list[MissingFact] = []
    if deadline is None:
        missing_facts.append(
            _missing_fact(
                "deadline",
                "Deadline is needed to calculate monthly or paycheck savings.",
                "Savings requirement and shortfall are unknown.",
            )
        )
    if current_saved_amount is None:
        missing_facts.append(
            _missing_fact(
                "current_saved_amount",
                "Current saved amount is needed to calculate the remaining gap.",
                "Savings requirement may be overstated.",
            )
        )

    saved = current_saved_amount or Decimal("0")
    remaining = max(target_amount - saved, Decimal("0"))
    months_remaining = _months_between(effective_today, deadline) if deadline is not None else None
    monthly_required = None
    paycheck_required = None
    if months_remaining is not None:
        monthly_required = remaining if months_remaining <= 0 else remaining / months_remaining
        paycheck_required = monthly_required / paychecks_per_month if paychecks_per_month > 0 else None

    likely_shortfall = None
    if planned_savings_per_month is not None and months_remaining is not None:
        likely_shortfall = max(
            remaining - (planned_savings_per_month * max(months_remaining, Decimal("0"))),
            Decimal("0"),
        )

    alternatives: list[dict[str, object]] = []
    if likely_shortfall is not None and likely_shortfall > 0 and monthly_required is not None:
        alternatives.append({"type": "increase_monthly_savings", "amount": _money(monthly_required)})
        alternatives.append({"type": "reduce_target", "amount": _money(target_amount - likely_shortfall)})
    if planned_savings_per_month is not None and planned_savings_per_month > 0 and deadline is not None:
        months_needed = math.ceil(remaining / planned_savings_per_month) if remaining > 0 else 0
        alternatives.append(
            {
                "type": "delay_deadline",
                "deadline": (effective_today + datetime.timedelta(days=months_needed * 30)).isoformat(),
            }
        )

    return {
        "target_amount": _money(target_amount),
        "deadline": deadline.isoformat() if deadline is not None else None,
        "current_saved_amount": _money(current_saved_amount) if current_saved_amount is not None else None,
        "monthly_savings_required": _money(monthly_required) if monthly_required is not None else None,
        "paycheck_savings_required": _money(paycheck_required) if paycheck_required is not None else None,
        "likely_shortfall": _money(likely_shortfall) if likely_shortfall is not None else None,
        "alternatives": alternatives,
        "missing_facts": missing_facts,
    }


def _currency_cache_key(source_currency: str, target_currency: str) -> str:
    return f"advisor_currency_rate:{source_currency.upper()}:{target_currency.upper()}"


def _fetch_frankfurter_rate(source_currency: str, target_currency: str) -> dict[str, object]:
    query = urllib.parse.urlencode({"amount": "1", "from": source_currency, "to": target_currency})
    request = urllib.request.Request(f"{_FRANKFURTER_BASE_URL}?{query}", method="GET")  # noqa: S310
    with urllib.request.urlopen(request, timeout=_FRANKFURTER_TIMEOUT_SECONDS) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    rates = cast(dict[str, object], payload.get("rates", {}))
    rate = Decimal(str(rates[target_currency]))
    return {
        "rate": rate,
        "rate_date": str(payload["date"]),
        "provider": "Frankfurter",
        "provider_url": _FRANKFURTER_BASE_URL,
    }


def convert_currency(*, amount: Decimal, source_currency: str, target_currency: str) -> dict[str, object]:
    source = source_currency.upper()
    target = target_currency.upper()
    if source == target:
        return {
            "status": "ok",
            "amount": _money(amount),
            "source_currency": source,
            "target_currency": target,
            "converted_amount": _money(amount),
            "rate": 1.0,
            "rate_date": timezone.localdate().isoformat(),
            "provider": {"name": "Frankfurter", "url": _FRANKFURTER_BASE_URL, "cached": False},
        }

    cache_key = _currency_cache_key(source, target)
    cached_rate = cache.get(cache_key)
    try:
        rate_payload = (
            cast(dict[str, object], cached_rate) if cached_rate is not None else _fetch_frankfurter_rate(source, target)
        )
        if cached_rate is None:
            cache.set(cache_key, rate_payload, _FRANKFURTER_CACHE_SECONDS)
        rate = Decimal(str(rate_payload["rate"]))
    except (InvalidOperation, KeyError, TypeError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {
            "status": "failed",
            "amount": _money(amount),
            "source_currency": source,
            "target_currency": target,
            "converted_amount": None,
            "error": str(exc),
            "provider": {"name": "Frankfurter", "url": _FRANKFURTER_BASE_URL, "cached": False},
        }

    return {
        "status": "ok",
        "amount": _money(amount),
        "source_currency": source,
        "target_currency": target,
        "converted_amount": _money(amount * rate),
        "rate": float(rate),
        "rate_date": str(rate_payload["rate_date"]),
        "provider": {
            "name": str(rate_payload["provider"]),
            "url": str(rate_payload["provider_url"]),
            "cached": cached_rate is not None,
        },
    }
