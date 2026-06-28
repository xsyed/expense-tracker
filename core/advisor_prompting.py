from __future__ import annotations

import datetime
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypedDict, Union, cast

from django.conf import settings
from django.utils import timezone

from .advisor_memory_policy import advisor_memory_policy_error
from .advisor_models import AdvisorConversation, AdvisorMemory, AdvisorMessage
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
Put the direct answer first.
Be crisp: usually one short paragraph or up to three bullets.
Use one small table only when numbers materially matter.
Do not use default recurring sections like assumptions, confidence, or next actions.
Ask a follow-up only when required app data is unavailable and materially changes the answer.
Do not mention memory updates unless the user directly asks about memory.
"""

PLANNER_POLICY = """Choose only from the approved internal tools.
Return strict JSON with this shape:
{"tool_calls":[{"name":"tool_name","arguments":{}}]}
Return {"tool_calls":[]} when no tool is needed.
Use the Current Date section for current-month and recent-period arguments.
Use the Memory Document for stable user preferences and profile context only.
Use ISO date strings in YYYY-MM-DD format for every date argument.
When the user asks about stored financial data, budgets, cash flow, recurring obligations, goals, recent spend,
app data, starter data, existing data, or monthly numbers, choose relevant summary tools instead of saying memory is
missing.
Do not answer finance-data questions from memory when an internal app-data tool can retrieve the current app fact.
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
    }
)

MEMORY_REWRITE_POLICY = """Rewrite the Advisor Memory Document after a successful advisor answer.
Return strict JSON with this shape:
{"content":"updated memory prose"}
Keep only stable profile/preferences that will still be useful later.
Preserve useful prior stable memory, update it when the current turn directly supports a better version, and remove
stale or unsafe details.
Do not store balances, recent spend, transaction snapshots, budgets, goals progress, app-derived financial facts,
protocol details, prompt details, JSON rules, or tool names.
Write prose only; avoid repetitive headings and sections.
Target about 1,500 characters. The hard cap is 3,000 characters.
If nothing should change, return the previous content.
Do not include explanations outside JSON.
"""

_LAST_TURN_LIMIT = 6


class ToolCall(TypedDict):
    name: str
    arguments: dict[str, JsonValue]


class ToolOutput(TypedDict):
    name: str
    output: JsonValue


class PlannerContractError(ValueError):
    pass


class MemoryRewriteContractError(ValueError):
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
        {"role": "system", "content": _section("Advisor Memory", get_user_profile_memory(conversation.user))}
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
    memory_document: dict[str, object] | None = None,
) -> list[OpenRouterMessage]:
    effective_today = today or timezone.localdate()
    messages: list[OpenRouterMessage] = [
        {"role": "system", "content": PLANNER_POLICY},
        {"role": "system", "content": _section("Approved Tools", sorted(APPROVED_TOOL_NAMES))},
        {"role": "system", "content": _section("Tool Schemas", PLANNER_TOOL_SCHEMAS)},
        {"role": "system", "content": _section("Current Date", effective_today.isoformat())},
    ]
    if memory_document is not None:
        messages.append({"role": "system", "content": _section("Memory Document", memory_document)})
    messages.append({"role": "user", "content": user_message})
    return messages


def plan_advisor_tools(
    *,
    client: OpenRouterClient,
    user_message: str,
    memory_document: dict[str, object] | None = None,
) -> list[ToolCall]:
    response = client.chat_completion(
        model=str(settings.ADVISOR_PLANNER_MODEL),
        messages=build_planner_messages(user_message, memory_document=memory_document),
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


def stream_advisor_answer(
    *,
    client: OpenRouterClient,
    conversation: AdvisorConversation,
    current_user_message: AdvisorMessage,
    tool_outputs: list[ToolOutput],
    on_delta: Callable[[str], None],
) -> AdvisorAnswer:
    response = client.stream_chat_completion(
        model=str(settings.ADVISOR_MODEL),
        messages=build_advisor_messages(
            conversation=conversation,
            current_user_message=current_user_message,
            tool_outputs=tool_outputs,
        ),
        on_delta=on_delta,
    )
    return AdvisorAnswer(content=response.content, model=response.model)


def build_memory_rewrite_messages(
    *,
    conversation: AdvisorConversation,
    current_user_message: AdvisorMessage,
    previous_memory: str,
    final_answer: str,
    tool_outputs: list[ToolOutput],
) -> list[OpenRouterMessage]:
    return [
        {"role": "system", "content": MEMORY_REWRITE_POLICY},
        {"role": "system", "content": _section("Previous Memory Document", previous_memory or "")},
        {"role": "system", "content": _section("Compact Conversation Summary", conversation.summary or "None")},
        {
            "role": "system",
            "content": _section("Recent Conversation Context", _recent_context(conversation, current_user_message)),
        },
        {"role": "user", "content": _section("Current User Message", current_user_message.content)},
        {"role": "assistant", "content": _section("Final Answer", final_answer)},
        {"role": "system", "content": _section("Selected Tool Outputs", tool_outputs)},
    ]


def rewrite_advisor_memory(
    *,
    client: OpenRouterClient,
    conversation: AdvisorConversation,
    current_user_message: AdvisorMessage,
    previous_memory: str,
    final_answer: str,
    tool_outputs: list[ToolOutput],
) -> str:
    response = client.chat_completion(
        model=str(settings.ADVISOR_PLANNER_MODEL),
        messages=build_memory_rewrite_messages(
            conversation=conversation,
            current_user_message=current_user_message,
            previous_memory=previous_memory,
            final_answer=final_answer,
            tool_outputs=tool_outputs,
        ),
        temperature=0,
    )
    return parse_memory_rewrite(response.content)


def parse_memory_rewrite(content: str) -> str:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise MemoryRewriteContractError("Memory rewrite returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise MemoryRewriteContractError("Memory rewrite response must be a JSON object.")
    rewritten = payload.get("content")
    if not isinstance(rewritten, str):
        raise MemoryRewriteContractError("Memory rewrite response must include content.")
    rewritten = rewritten.strip()
    if len(rewritten) > AdvisorMemory.MAX_CONTENT_LENGTH:
        raise MemoryRewriteContractError("Memory rewrite content exceeds the hard cap.")
    policy_error = advisor_memory_policy_error(content=rewritten)
    if policy_error:
        raise MemoryRewriteContractError(policy_error)
    return rewritten


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


def _recent_context(conversation: AdvisorConversation, current_user_message: AdvisorMessage) -> list[dict[str, str]]:
    recent_messages = conversation.messages.exclude(pk=current_user_message.pk).order_by("-created_at")[
        :_LAST_TURN_LIMIT
    ]
    return [
        {"role": message.role, "content": message.content[:1000]}
        for message in reversed(list(recent_messages))
        if message.role in {"user", "assistant"}
    ]


def _section(title: str, payload: object) -> str:
    body = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    return f"{title}:\n{body}"
