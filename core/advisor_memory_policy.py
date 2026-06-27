from __future__ import annotations

import re

FINANCIAL_RECORD_KEY_PREFIXES = (
    "account",
    "budget",
    "category",
    "expense_month",
    "goal",
    "goal_contribution",
    "transaction",
)

POLICY_ERROR = "Advisor Memory must be stable personal context, not transaction-derived amounts or activity."

_BLOCKED_KEY_PARTS = (
    "salary",
    "payroll",
    "rent_amount",
    "monthly_rent",
    "category_spend",
    "spending_total",
    "spend_total",
    "current_balance",
    "account_balance",
    "credit_card_balance",
    "recent_purchase",
    "recent_purchases",
    "last_purchase",
)
_DERIVED_PHRASES = (
    "transaction-derived",
    "derived from transaction",
    "derived from transactions",
    "inferred from transaction",
    "inferred from transactions",
    "from transaction history",
    "from transactions",
    "based on transactions",
    "based on spending",
    "spending history",
    "category spend",
    "recent purchase",
    "recent purchases",
    "last week's",
    "last week",
    "last month",
    "current balance",
    "credit card balance",
)
_RENT_AMOUNT_RE = re.compile(r"\b(?:monthly\s+)?rent\s*(?:is|=|:|amount)?\s*(?:[$]\s*)?\d{3,}", re.IGNORECASE)
_SALARY_AMOUNT_RE = re.compile(
    r"\b(?:salary|payroll|paycheque|paycheck|income)\b.{0,40}(?:[$]\s*)?\d{3,}",
    re.IGNORECASE,
)
_BALANCE_RE = re.compile(
    r"\b(?:current\s+)?(?:account|credit card|cash|emergency fund|bank)?\s*balance\b",
    re.IGNORECASE,
)
_SPEND_RE = re.compile(
    r"\b(?:category\s+spend|spent\s+(?:last|this)|last\s+(?:week|month).{0,40}(?:spend|spent|purchase))\b",
    re.IGNORECASE,
)


def advisor_memory_policy_error(*, key: str, value: str, rationale: str = "") -> str:
    normalized_key = _normalize_key(key)
    if normalized_key.startswith(FINANCIAL_RECORD_KEY_PREFIXES):
        return POLICY_ERROR
    if any(part in normalized_key for part in _BLOCKED_KEY_PARTS):
        return POLICY_ERROR

    text = _normalize_text(" ".join([key, value, rationale]))
    if any(phrase in text for phrase in _DERIVED_PHRASES):
        return POLICY_ERROR
    if _RENT_AMOUNT_RE.search(text) or _SALARY_AMOUNT_RE.search(text):
        return POLICY_ERROR
    if _BALANCE_RE.search(text) or _SPEND_RE.search(text):
        return POLICY_ERROR
    return ""


def _normalize_key(value: str) -> str:
    return value.lower().replace("-", "_").replace(" ", "_")


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().split())
