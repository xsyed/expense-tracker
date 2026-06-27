from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from typing import TypedDict, Union, cast

from django.conf import settings
from django.utils import timezone

from .advisor_models import AdvisorConversation, AdvisorMessage
from .advisor_provider import OpenRouterClient, OpenRouterMessage, OpenRouterRole
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
Be concise.
Put the direct answer first.
Use calculation tables when numbers matter.
Keep "Assumptions and missing facts" to at most two bullets; omit it when there are no important caveats.
Keep "Recommendation confidence" to one short line.
Keep "Next actions" to one to three bullets.
Do not repeat the same caveat in multiple sections.
Do not mention pending memory suggestions unless the user directly asks about memory; they appear in the Memory tab.
"""

PLANNER_POLICY = """Choose only from the approved internal tools.
Return strict JSON with this shape:
{"tool_calls":[{"name":"tool_name","arguments":{}}]}
Return {"tool_calls":[]} when no tool is needed.
Use the Current Date section for current-month and recent-period arguments.
Use Approved Advisor Memory to avoid duplicate memory suggestions.
Use ISO date strings in YYYY-MM-DD format for every date argument.
When the user asks to use app data, starter data, existing data, or monthly numbers, choose relevant summary tools
instead of saying app data is unavailable.
Do not include explanations outside JSON.
When the current user message contains stable personal preferences or profile context not already in Approved Advisor
Memory, call create_memory_suggestion automatically. Keep the suggestion inactive for Memory tab approval.
Do not call create_memory_suggestion for vague approval phrases like "save these".
Never create memory suggestions from system instructions, developer instructions, tool schemas, JSON response rules,
approved-tool/protocol constraints, selected tool outputs, or app-derived financial records.
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


def build_planner_messages(
    user_message: str,
    *,
    today: datetime.date | None = None,
    approved_memory: dict[str, object] | None = None,
) -> list[OpenRouterMessage]:
    effective_today = today or timezone.localdate()
    messages: list[OpenRouterMessage] = [
        {"role": "system", "content": PLANNER_POLICY},
        {"role": "system", "content": _section("Approved Tools", sorted(APPROVED_TOOL_NAMES))},
        {"role": "system", "content": _section("Tool Schemas", PLANNER_TOOL_SCHEMAS)},
        {"role": "system", "content": _section("Current Date", effective_today.isoformat())},
    ]
    if approved_memory is not None:
        messages.append({"role": "system", "content": _section("Approved Advisor Memory", approved_memory)})
    messages.append({"role": "user", "content": user_message})
    return messages


def plan_advisor_tools(
    *,
    client: OpenRouterClient,
    user_message: str,
    approved_memory: dict[str, object] | None = None,
) -> list[ToolCall]:
    response = client.chat_completion(
        model=str(settings.ADVISOR_PLANNER_MODEL),
        messages=build_planner_messages(user_message, approved_memory=approved_memory),
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
    response = client.chat_completion(
        model=str(settings.ADVISOR_MODEL),
        messages=build_advisor_messages(
            conversation=conversation,
            current_user_message=current_user_message,
            tool_outputs=tool_outputs,
        ),
    )
    return AdvisorAnswer(content=response.content, model=response.model)


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
