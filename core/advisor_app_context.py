from __future__ import annotations

from django.utils import timezone

from .advisor_prompting import ToolCall
from .models import AdvisorMemory
from .models import User as UserModel

_BASELINE_APP_DATA_TERMS = (
    "starter budget",
    "starter data",
    "first request",
    "get started",
    "from the app",
    "app data",
    "app itself",
    "ask the app",
    "use the app",
    "use my app",
    "use my data",
    "existing data",
    "stored data",
    "monthly numbers",
    "budget template",
)
_HIGH_IMPACT_TERMS = (
    "afford",
    "buy a car",
    "buy this car",
    "vehicle",
    "lend money",
    "job loss",
    "emergency fund",
    "marriage",
    "wedding",
    "large event",
    "support my spouse",
    "move money",
    "every paycheck",
)
_ADVICE_CONTEXT_TERMS = (
    "advice",
    "afford",
    "budget",
    "buy",
    "can i",
    "cash",
    "debt",
    "emergency",
    "expense",
    "goal",
    "income",
    "month",
    "recommend",
    "save",
    "saving",
    "should i",
    "spend",
)


def baseline_app_data_tool_calls(user: UserModel, user_message: str) -> list[ToolCall]:
    if not _needs_baseline_app_data(user, user_message):
        return []

    today = timezone.localdate()
    return [
        {"name": "get_user_profile_memory", "arguments": {}},
        {"name": "get_cash_flow_summary", "arguments": {"months": 6, "end_month": today.isoformat()}},
        {"name": "get_budget_position", "arguments": {"month": today.isoformat()}},
        {"name": "get_recurring_obligations", "arguments": {}},
        {"name": "get_goal_status", "arguments": {"today": today.isoformat()}},
        {"name": "get_recent_spending_brief", "arguments": {"preset": "this_month"}},
    ]


def _needs_baseline_app_data(user: UserModel, user_message: str) -> bool:
    normalized = " ".join(user_message.lower().split())
    if any(term in normalized for term in _BASELINE_APP_DATA_TERMS):
        return True
    if any(term in normalized for term in _HIGH_IMPACT_TERMS):
        return True
    return not _has_approved_memory(user) and any(term in normalized for term in _ADVICE_CONTEXT_TERMS)


def _has_approved_memory(user: UserModel) -> bool:
    return AdvisorMemory.objects.filter(user=user).exclude(content="").exists()
