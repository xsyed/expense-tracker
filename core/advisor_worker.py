from __future__ import annotations

import datetime
import json
from decimal import Decimal
from typing import Literal, TypedDict, Union, cast

from django.db import transaction
from django.utils import timezone

from .advisor_app_context import baseline_app_data_tool_calls
from .advisor_calculation_tools import (
    convert_currency,
    run_affordability_check,
    run_emergency_fund_calculation,
    run_large_event_plan,
)
from .advisor_memory import get_advisor_memory, save_advisor_memory
from .advisor_prompting import (
    ToolCall,
    ToolOutput,
    generate_advisor_answer,
    plan_advisor_tools,
    rewrite_advisor_memory,
)
from .advisor_provider import OpenRouterClient
from .advisor_tools import (
    get_budget_position,
    get_cash_flow_summary,
    get_goal_status,
    get_recent_spending_brief,
    get_recurring_obligations,
    get_user_profile_memory,
)
from .models import AdvisorMessage, AdvisorRun
from .models import User as UserModel

JsonValue = Union[None, bool, int, float, str, list["JsonValue"], dict[str, "JsonValue"]]
DatePreset = Literal["last_7_days", "this_month", "previous_month"]

STALE_RUNNING_AFTER = datetime.timedelta(minutes=15)
SUMMARY_TOOL_NAMES = frozenset(
    {
        "get_user_profile_memory",
        "get_recent_spending_brief",
        "get_budget_position",
        "get_cash_flow_summary",
        "get_recurring_obligations",
        "get_goal_status",
    }
)
CALCULATION_TOOL_NAMES = frozenset(
    {
        "run_affordability_check",
        "run_emergency_fund_calculation",
        "run_large_event_plan",
        "convert_currency",
    }
)


class ToolTraceEntry(TypedDict, total=False):
    name: str
    status: str
    argument_keys: list[str]
    output_keys: list[str]
    error: str


def mark_stale_running_runs(*, stale_after: datetime.timedelta = STALE_RUNNING_AFTER) -> int:
    cutoff = timezone.now() - stale_after
    return AdvisorRun.objects.filter(status=AdvisorRun.STATUS_RUNNING, updated_at__lt=cutoff).update(
        status=AdvisorRun.STATUS_FAILED,
        error_message="Run was marked failed because the worker stopped while it was running.",
    )


def process_next_advisor_run(*, client: OpenRouterClient | None = None) -> bool:
    run = _claim_next_run()
    if run is None:
        return False
    process_advisor_run(run_id=run.id, client=client)
    return True


def process_advisor_run(*, run_id: int, client: OpenRouterClient | None = None) -> None:
    effective_client = client or OpenRouterClient()
    run = _get_run(run_id)
    if run.status == AdvisorRun.STATUS_CANCELED:
        return
    if run.status != AdvisorRun.STATUS_RUNNING:
        raise ValueError("Advisor run must be running before processing.")

    tool_outputs: list[ToolOutput] = []
    try:
        _save_partial(run, "Planning advisor answer...")
        memory_document = get_user_profile_memory(run.conversation.user)
        planned_tool_calls = plan_advisor_tools(
            client=effective_client,
            user_message=run.user_message.content,
            memory_document=memory_document,
        )
        tool_calls = _merge_tool_calls(
            baseline_app_data_tool_calls(run.conversation.user, run.user_message.content),
            planned_tool_calls,
        )
        _stop_if_canceled(run)
        tool_outputs, tool_trace = _execute_tool_calls(run, tool_calls)
        _save_trace(run, tool_trace)
        _stop_if_canceled(run)
        _save_partial(run, "Drafting advisor response...")
        answer = generate_advisor_answer(
            client=effective_client,
            conversation=run.conversation,
            current_user_message=run.user_message,
            tool_outputs=tool_outputs,
        )
        _stop_if_canceled(run)
    except Exception as exc:
        _mark_failed(run, str(exc))
        return

    run.final_response = answer.content
    run.model = answer.model
    run.error_message = ""
    if answer.follow_up_required:
        run.status = AdvisorRun.STATUS_WAITING_FOR_USER
        run.save(update_fields=["final_response", "model", "error_message", "status", "updated_at"])
        return

    run.status = AdvisorRun.STATUS_COMPLETED
    run.save(update_fields=["final_response", "model", "error_message", "status", "updated_at"])
    AdvisorMessage.objects.create(
        conversation=run.conversation,
        role=AdvisorMessage.ROLE_ASSISTANT,
        content=answer.content,
        linked_run=run,
    )
    _silently_rewrite_memory(client=effective_client, run=run, tool_outputs=tool_outputs)


def cancel_advisor_run(*, run_id: int) -> bool:
    updated = AdvisorRun.objects.filter(
        pk=run_id,
        status__in=[AdvisorRun.STATUS_PENDING, AdvisorRun.STATUS_RUNNING],
    ).update(status=AdvisorRun.STATUS_CANCELED)
    return updated > 0


def _claim_next_run() -> AdvisorRun | None:
    with transaction.atomic():
        run = (
            AdvisorRun.objects.select_for_update()
            .select_related("conversation", "user_message", "conversation__user")
            .filter(status=AdvisorRun.STATUS_PENDING)
            .order_by("created_at")
            .first()
        )
        if run is None:
            return None
        run.status = AdvisorRun.STATUS_RUNNING
        run.error_message = ""
        run.save(update_fields=["status", "error_message", "updated_at"])
        return run


def _get_run(run_id: int) -> AdvisorRun:
    return AdvisorRun.objects.select_related("conversation", "user_message", "conversation__user").get(pk=run_id)


def _save_partial(run: AdvisorRun, text: str) -> None:
    run.partial_response = text
    run.save(update_fields=["partial_response", "updated_at"])


def _save_trace(run: AdvisorRun, trace: list[ToolTraceEntry]) -> None:
    run.tool_trace = trace
    run.save(update_fields=["tool_trace", "updated_at"])


def _mark_failed(run: AdvisorRun, message: str) -> None:
    fresh_run = AdvisorRun.objects.get(pk=run.pk)
    if fresh_run.status == AdvisorRun.STATUS_CANCELED:
        return
    fresh_run.status = AdvisorRun.STATUS_FAILED
    fresh_run.error_message = message
    fresh_run.save(update_fields=["status", "error_message", "updated_at"])


def _stop_if_canceled(run: AdvisorRun) -> None:
    run.refresh_from_db(fields=["status"])
    if run.status == AdvisorRun.STATUS_CANCELED:
        raise AdvisorRunCanceledError


class AdvisorRunCanceledError(RuntimeError):
    pass


def _merge_tool_calls(baseline_calls: list[ToolCall], planned_calls: list[ToolCall]) -> list[ToolCall]:
    merged: list[ToolCall] = []
    seen: set[tuple[str, str]] = set()
    for tool_call in [*baseline_calls, *planned_calls]:
        signature = _tool_call_signature(tool_call)
        if signature in seen:
            continue
        merged.append(tool_call)
        seen.add(signature)
    return merged


def _tool_call_signature(tool_call: ToolCall) -> tuple[str, str]:
    return tool_call["name"], json.dumps(tool_call["arguments"], sort_keys=True)


def _execute_tool_calls(run: AdvisorRun, tool_calls: list[ToolCall]) -> tuple[list[ToolOutput], list[ToolTraceEntry]]:
    outputs: list[ToolOutput] = []
    trace: list[ToolTraceEntry] = []
    user = run.conversation.user
    for tool_call in tool_calls:
        name = tool_call["name"]
        arguments = tool_call["arguments"]
        try:
            output = _execute_tool_call(name=name, arguments=arguments, user=user)
        except Exception as exc:
            trace.append(
                {
                    "name": name,
                    "status": "failed",
                    "argument_keys": sorted(arguments),
                    "error": str(exc),
                }
            )
            raise
        outputs.append({"name": name, "output": cast(JsonValue, output)})
        trace.append(
            {
                "name": name,
                "status": "completed",
                "argument_keys": sorted(arguments),
                "output_keys": sorted(output) if isinstance(output, dict) else [],
            }
        )
        _stop_if_canceled(run)
    return outputs, trace


def _execute_tool_call(
    *,
    name: str,
    arguments: dict[str, JsonValue],
    user: UserModel,
) -> dict[str, object]:
    if name in SUMMARY_TOOL_NAMES:
        return _execute_summary_tool(name=name, arguments=arguments, user=user)
    if name in CALCULATION_TOOL_NAMES:
        return _execute_calculation_tool(name=name, arguments=arguments)
    raise ValueError(f"Unsupported advisor tool: {name}")


def _silently_rewrite_memory(*, client: OpenRouterClient, run: AdvisorRun, tool_outputs: list[ToolOutput]) -> None:
    memory = get_advisor_memory(run.conversation.user)
    try:
        content = rewrite_advisor_memory(
            client=client,
            conversation=run.conversation,
            current_user_message=run.user_message,
            previous_memory=memory.content,
            final_answer=run.final_response,
            tool_outputs=tool_outputs,
        )
        if content != memory.content:
            save_advisor_memory(run.conversation.user, content)
    except Exception:
        return


def _execute_summary_tool(*, name: str, arguments: dict[str, JsonValue], user: UserModel) -> dict[str, object]:
    if name == "get_user_profile_memory":
        return get_user_profile_memory(user)
    if name == "get_recent_spending_brief":
        preset = _preset_arg(arguments, "preset")
        start_date = _optional_date_arg(arguments, "start_date")
        end_date = _optional_date_arg(arguments, "end_date")
        if preset is None and start_date is None and end_date is None:
            preset = "this_month"
        return get_recent_spending_brief(
            user,
            preset=preset,
            start_date=start_date,
            end_date=end_date,
            include_evidence=_bool_arg(arguments, "include_evidence", False),
            evidence_limit=_int_arg(arguments, "evidence_limit", 10),
        )
    if name == "get_budget_position":
        return get_budget_position(user, month=_date_arg(arguments, "month", timezone.localdate()))
    if name == "get_cash_flow_summary":
        return get_cash_flow_summary(
            user,
            months=_int_arg(arguments, "months", 6),
            end_month=_optional_date_arg(arguments, "end_month"),
        )
    if name == "get_recurring_obligations":
        return get_recurring_obligations(user, limit=_int_arg(arguments, "limit", 20))
    if name == "get_goal_status":
        return get_goal_status(
            user,
            goal_id=_optional_int_arg(arguments, "goal_id"),
            today=_optional_date_arg(arguments, "today"),
        )
    raise ValueError(f"Unsupported advisor summary tool: {name}")


def _execute_calculation_tool(*, name: str, arguments: dict[str, JsonValue]) -> dict[str, object]:
    if name == "run_affordability_check":
        return run_affordability_check(
            amount=_decimal_arg(arguments, "amount"),
            expected_monthly_surplus=_optional_decimal_arg(arguments, "expected_monthly_surplus"),
            current_available_cash=_optional_decimal_arg(arguments, "current_available_cash"),
            minimum_reserve=_optional_decimal_arg(arguments, "minimum_reserve"),
            monthly_payment=_decimal_arg(arguments, "monthly_payment", Decimal("0")),
            required_upfront_cash=_optional_decimal_arg(arguments, "required_upfront_cash"),
        )
    if name == "run_emergency_fund_calculation":
        return run_emergency_fund_calculation(
            monthly_essential_expenses=_decimal_arg(arguments, "monthly_essential_expenses"),
            required_months=_decimal_arg(arguments, "required_months"),
            current_emergency_savings=_optional_decimal_arg(arguments, "current_emergency_savings"),
            savings_amount_per_period=_optional_decimal_arg(arguments, "savings_amount_per_period"),
            savings_period=_period_arg(arguments, "savings_period", "monthly"),
            today=_optional_date_arg(arguments, "today"),
        )
    if name == "run_large_event_plan":
        return run_large_event_plan(
            target_amount=_decimal_arg(arguments, "target_amount"),
            deadline=_optional_date_arg(arguments, "deadline"),
            current_saved_amount=_optional_decimal_arg(arguments, "current_saved_amount"),
            planned_savings_per_month=_optional_decimal_arg(arguments, "planned_savings_per_month"),
            paychecks_per_month=_decimal_arg(arguments, "paychecks_per_month", Decimal("2")),
            today=_optional_date_arg(arguments, "today"),
        )
    if name == "convert_currency":
        return convert_currency(
            amount=_decimal_arg(arguments, "amount"),
            source_currency=_string_arg(arguments, "source_currency", _string_arg(arguments, "from_currency", "CAD")),
            target_currency=_string_arg(arguments, "target_currency", _string_arg(arguments, "to_currency", "CAD")),
        )
    raise ValueError(f"Unsupported advisor calculation tool: {name}")


def _string_arg(arguments: dict[str, JsonValue], name: str, default: str | None = None) -> str:
    value = arguments.get(name, default)
    if isinstance(value, str):
        return value
    raise ValueError(f"{name} must be a string.")


def _int_arg(arguments: dict[str, JsonValue], name: str, default: int | None = None) -> int:
    value = arguments.get(name, default)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ValueError(f"{name} must be an integer.")


def _optional_int_arg(arguments: dict[str, JsonValue], name: str) -> int | None:
    value = arguments.get(name)
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ValueError(f"{name} must be an integer.")


def _bool_arg(arguments: dict[str, JsonValue], name: str, default: bool) -> bool:
    value = arguments.get(name, default)
    if isinstance(value, bool):
        return value
    raise ValueError(f"{name} must be a boolean.")


def _decimal_arg(arguments: dict[str, JsonValue], name: str, default: Decimal | None = None) -> Decimal:
    value = arguments.get(name)
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"{name} is required.")
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{name} must be numeric.")
    return Decimal(str(value))


def _optional_decimal_arg(arguments: dict[str, JsonValue], name: str) -> Decimal | None:
    if arguments.get(name) is None:
        return None
    return _decimal_arg(arguments, name)


def _date_arg(arguments: dict[str, JsonValue], name: str, default: datetime.date | None = None) -> datetime.date:
    value = arguments.get(name)
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"{name} must be a string.")
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string.")
    return datetime.date.fromisoformat(value)


def _optional_date_arg(arguments: dict[str, JsonValue], name: str) -> datetime.date | None:
    if arguments.get(name) is None:
        return None
    return _date_arg(arguments, name)


def _preset_arg(arguments: dict[str, JsonValue], name: str) -> DatePreset | None:
    value = arguments.get(name)
    if value is None:
        return None
    if value in {"last_7_days", "this_month", "previous_month"}:
        return cast(DatePreset, value)
    raise ValueError(f"{name} must be an approved date preset.")


def _period_arg(
    arguments: dict[str, JsonValue], name: str, default: Literal["monthly", "paycheck"]
) -> Literal[
    "monthly",
    "paycheck",
]:
    value = arguments.get(name, default)
    if value in {"monthly", "paycheck"}:
        return cast(Literal["monthly", "paycheck"], value)
    raise ValueError(f"{name} must be monthly or paycheck.")
