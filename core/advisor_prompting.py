from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from typing import TypedDict, Union, cast

from django.conf import settings
from django.utils import timezone

from .advisor_models import AdvisorConversation, AdvisorMessage
from .advisor_provider import OpenRouterClient, OpenRouterError, OpenRouterMessage, OpenRouterRole
from .advisor_tools import get_user_profile_memory

JsonValue = Union[None, bool, int, float, str, list["JsonValue"], dict[str, "JsonValue"]]

SYSTEM_POLICY = """You are the Personal Finance Copilot for a user's private expense tracker.

You may give budgeting, spending, saving, and cash-flow recommendations when they are grounded in provided tool output.
You may say no when the math says no.
You must not present regulated investment, tax, legal, insurance, immigration, lending-contract, or securities
advice as authoritative.
For regulated topics, explain general tradeoffs, identify missing facts, and recommend a qualified professional.

Phase 1 cannot update financial records, browse the web, ingest PDFs or articles, process CSV/image/video
attachments, execute arbitrary model-written code, use external MCP tools, or search raw transaction history by default.
Use only approved internal tool outputs supplied in this run.
"""

RESPONSE_POLICY = """Return Markdown only.
Put the direct answer first.
Include assumptions and missing facts.
Include a calculation table when numbers matter.
Include recommendation confidence.
Include next actions.
If memory suggestions are present, separate them from the answer under "Memory suggestions".
"""

PLANNER_POLICY = """Choose only from the approved internal tools.
Return strict JSON with this shape:
{"tool_calls":[{"name":"tool_name","arguments":{}}]}
Return {"tool_calls":[]} when no tool is needed.
Use the Current Date section for current-month and recent-period arguments.
Use ISO date strings in YYYY-MM-DD format for every date argument.
When the user asks to use app data, starter data, existing data, or monthly numbers, choose relevant summary tools
instead of saying app data is unavailable.
Do not include explanations outside JSON.
"""

PLANNER_TOOL_SCHEMAS = """Tool argument schemas:
- get_user_profile_memory: {"limit": integer, optional}
- get_recent_spending_brief: {"preset": "last_7_days"|"this_month"|"previous_month"} or
  {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "include_evidence": boolean, optional}
- get_budget_position: {"month": "YYYY-MM-DD"}
- get_cash_flow_summary: {"months": integer 1-12, "end_month": "YYYY-MM-DD", optional}
- get_recurring_obligations: {"limit": integer, optional}
- get_goal_status: {"goal_id": integer, optional, "today": "YYYY-MM-DD", optional}
- run_affordability_check: {"amount": number, "expected_monthly_surplus": number, optional,
  "current_available_cash": number, optional, "minimum_reserve": number, optional,
  "monthly_payment": number, optional, "required_upfront_cash": number, optional}
- run_emergency_fund_calculation: {"monthly_essential_expenses": number, "required_months": number,
  "current_emergency_savings": number, optional, "savings_amount_per_period": number, optional,
  "savings_period": "monthly"|"paycheck", optional, "today": "YYYY-MM-DD", optional}
- run_large_event_plan: {"target_amount": number, "deadline": "YYYY-MM-DD", optional,
  "current_saved_amount": number, optional, "planned_savings_per_month": number, optional,
  "paychecks_per_month": number, optional, "today": "YYYY-MM-DD", optional}
- convert_currency: {"amount": number, "source_currency": string, "target_currency": string}
- create_memory_suggestion: {"key": string, "suggested_value": string, "rationale": string}
"""

APPROVED_TOOL_NAMES = frozenset(
    {
        "get_user_profile_memory",
        "get_recent_spending_brief",
        "get_budget_position",
        "get_cash_flow_summary",
        "get_recurring_obligations",
        "get_goal_status",
        "run_affordability_check",
        "run_emergency_fund_calculation",
        "run_large_event_plan",
        "convert_currency",
        "create_memory_suggestion",
    }
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
_LAST_TURN_LIMIT = 6


class ToolCall(TypedDict):
    name: str
    arguments: dict[str, JsonValue]


class ToolOutput(TypedDict):
    name: str
    output: JsonValue


class PlannerContractError(ValueError):
    pass


@dataclass(frozen=True)
class AdvisorAnswer:
    content: str
    model: str
    follow_up_required: bool = False


def build_advisor_messages(
    *,
    conversation: AdvisorConversation,
    current_user_message: AdvisorMessage,
    tool_outputs: list[ToolOutput],
) -> list[OpenRouterMessage]:
    messages: list[OpenRouterMessage] = [{"role": "system", "content": SYSTEM_POLICY}]
    messages.append(
        {"role": "system", "content": _section("Approved Advisor Memory", get_user_profile_memory(conversation.user))}
    )
    messages.append(
        {"role": "system", "content": _section("Compact Conversation Summary", conversation.summary or "None")}
    )
    messages.extend(_recent_turn_messages(conversation, current_user_message))
    messages.append({"role": "user", "content": _section("Current User Message", current_user_message.content)})
    messages.append({"role": "system", "content": _section("Selected Tool Outputs", tool_outputs)})
    messages.append({"role": "system", "content": RESPONSE_POLICY})
    return messages


def build_planner_messages(user_message: str, *, today: datetime.date | None = None) -> list[OpenRouterMessage]:
    effective_today = today or timezone.localdate()
    return [
        {"role": "system", "content": PLANNER_POLICY},
        {"role": "system", "content": _section("Approved Tools", sorted(APPROVED_TOOL_NAMES))},
        {"role": "system", "content": _section("Tool Schemas", PLANNER_TOOL_SCHEMAS)},
        {"role": "system", "content": _section("Current Date", effective_today.isoformat())},
        {"role": "user", "content": user_message},
    ]


def plan_advisor_tools(*, client: OpenRouterClient, user_message: str) -> list[ToolCall]:
    response = client.chat_completion(
        model=str(settings.ADVISOR_PLANNER_MODEL),
        messages=build_planner_messages(user_message),
        temperature=0,
    )
    return parse_planner_tool_calls(response.content)


def parse_planner_tool_calls(content: str) -> list[ToolCall]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise PlannerContractError("Planner returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise PlannerContractError("Planner response must be a JSON object.")
    raw_calls = payload.get("tool_calls")
    if not isinstance(raw_calls, list):
        raise PlannerContractError("Planner response must include tool_calls.")
    calls: list[ToolCall] = []
    for raw_call in raw_calls:
        calls.append(_parse_tool_call(raw_call))
    return calls


def generate_advisor_answer(
    *,
    client: OpenRouterClient,
    conversation: AdvisorConversation,
    current_user_message: AdvisorMessage,
    tool_outputs: list[ToolOutput],
) -> AdvisorAnswer:
    if requires_follow_up_gate(current_user_message.content, tool_outputs):
        return AdvisorAnswer(
            content=_follow_up_markdown(tool_outputs),
            model="follow-up-gate",
            follow_up_required=True,
        )
    response = client.chat_completion(
        model=str(settings.ADVISOR_MODEL),
        messages=build_advisor_messages(
            conversation=conversation,
            current_user_message=current_user_message,
            tool_outputs=tool_outputs,
        ),
    )
    return AdvisorAnswer(content=response.content, model=response.model)


def requires_follow_up_gate(user_message: str, tool_outputs: list[ToolOutput]) -> bool:
    normalized = user_message.lower()
    return any(term in normalized for term in _HIGH_IMPACT_TERMS) and bool(_missing_facts_from_outputs(tool_outputs))


def _parse_tool_call(raw_call: object) -> ToolCall:
    if not isinstance(raw_call, dict):
        raise PlannerContractError("Planner tool call must be an object.")
    name = raw_call.get("name")
    if not isinstance(name, str):
        raise PlannerContractError("Planner tool call name must be a string.")
    if name not in APPROVED_TOOL_NAMES:
        raise PlannerContractError(f"Planner requested unapproved tool: {name}")
    raw_arguments = raw_call.get("arguments", {})
    if not isinstance(raw_arguments, dict):
        raise PlannerContractError("Planner tool call arguments must be an object.")
    return {"name": name, "arguments": cast(dict[str, JsonValue], raw_arguments)}


def _recent_turn_messages(
    conversation: AdvisorConversation,
    current_user_message: AdvisorMessage,
) -> list[OpenRouterMessage]:
    recent_messages = conversation.messages.exclude(pk=current_user_message.pk).order_by("-created_at")[
        :_LAST_TURN_LIMIT
    ]
    return [
        {"role": cast(OpenRouterRole, message.role), "content": _section("Recent Conversation Turn", message.content)}
        for message in reversed(list(recent_messages))
        if message.role in {"user", "assistant"}
    ]


def _section(title: str, payload: object) -> str:
    body = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    return f"{title}:\n{body}"


def _missing_facts_from_outputs(tool_outputs: list[ToolOutput]) -> list[str]:
    missing: list[str] = []
    for output in tool_outputs:
        missing.extend(_missing_facts_from_value(output["output"]))
    return missing


def _missing_facts_from_value(value: JsonValue) -> list[str]:
    if isinstance(value, dict):
        names: list[str] = []
        missing_facts = value.get("missing_facts")
        if isinstance(missing_facts, list):
            names.extend(_missing_fact_names(missing_facts))
        for nested_value in value.values():
            names.extend(_missing_facts_from_value(nested_value))
        return names
    if isinstance(value, list):
        names = []
        for item in value:
            names.extend(_missing_facts_from_value(item))
        return names
    return []


def _missing_fact_names(items: list[JsonValue]) -> list[str]:
    names: list[str] = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str):
                names.append(name)
    return names


def _follow_up_markdown(tool_outputs: list[ToolOutput]) -> str:
    missing_names = sorted(set(_missing_facts_from_outputs(tool_outputs)))
    if not missing_names:
        raise OpenRouterError("Follow-up gate requires missing facts.")
    facts = "\n".join(f"- `{name}`" for name in missing_names)
    return (
        "I need a few facts before making a recommendation.\n\n"
        "## Missing facts\n"
        f"{facts}\n\n"
        "## Recommendation confidence\n"
        "Low until these facts are known.\n\n"
        "## Next actions\n"
        "Send the missing facts and I will calculate the recommendation."
    )
