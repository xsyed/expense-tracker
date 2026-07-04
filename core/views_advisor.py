from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Union, cast

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from .advisor_memory import get_advisor_memory, save_advisor_memory
from .advisor_worker import cancel_advisor_run
from .models import AdvisorConversation, AdvisorMemory, AdvisorMessage, AdvisorRun
from .models import User as UserModel

JsonValue = Union[None, bool, int, float, str, list["JsonValue"], dict[str, "JsonValue"]]
JsonObject = dict[str, JsonValue]

RECENT_CONVERSATION_LIMIT = 10
NEW_CONVERSATION_TITLE = "New conversation"
CONVERSATION_TITLE_MAX_LENGTH = 80
CONVERSATION_TITLE_PREFIX_LENGTH = 77
SSE_POLL_SECONDS = 0.5
SSE_HEARTBEAT_SECONDS = 10.0
TERMINAL_RUN_STATUSES = frozenset(
    {
        AdvisorRun.STATUS_COMPLETED,
        AdvisorRun.STATUS_WAITING_FOR_USER,
        AdvisorRun.STATUS_FAILED,
        AdvisorRun.STATUS_CANCELED,
    }
)


@login_required
@require_GET
def advisor_bootstrap_view(request: HttpRequest) -> JsonResponse:
    user = _request_user(request)
    conversations = AdvisorConversation.objects.filter(user=user, is_archived=False).order_by("-updated_at")
    active_conversation = conversations.first()

    return JsonResponse(
        {
            "active_conversation": _serialize_conversation(active_conversation) if active_conversation else None,
            "recent_conversations": [
                _serialize_conversation(item) for item in conversations[:RECENT_CONVERSATION_LIMIT]
            ],
            "pending_runs": [_serialize_run(item) for item in _pending_runs(user)],
            "memory": _serialize_memory(get_advisor_memory(user)),
        }
    )


@login_required
def advisor_conversations_view(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        conversations = AdvisorConversation.objects.filter(user=_request_user(request)).order_by("-updated_at")
        return JsonResponse({"conversations": [_serialize_conversation(item) for item in conversations]})
    if request.method == "POST":
        payload = _json_body(request)
        if payload is None:
            return _error_response("Invalid request body.")
        title = _clean_string(payload.get("title"), NEW_CONVERSATION_TITLE, max_length=200)
        conversation = AdvisorConversation.objects.create(user=_request_user(request), title=title)
        return JsonResponse({"conversation": _serialize_conversation(conversation)}, status=201)
    return _method_not_allowed(["GET", "POST"])


@login_required
@require_GET
def advisor_conversation_detail_view(request: HttpRequest, pk: int) -> JsonResponse:
    conversation = _get_user_conversation(_request_user(request), pk)
    messages = AdvisorMessage.objects.filter(conversation=conversation).select_related("linked_run")
    runs = AdvisorRun.objects.filter(conversation=conversation).select_related("user_message")
    return JsonResponse(
        {
            "conversation": _serialize_conversation(conversation),
            "messages": [_serialize_message(item) for item in messages],
            "runs": [_serialize_run(item) for item in runs],
        }
    )


@login_required
@require_POST
def advisor_message_create_view(request: HttpRequest, pk: int) -> JsonResponse:
    user = _request_user(request)
    conversation = _get_user_conversation(user, pk)
    payload = _json_body(request)
    if payload is None:
        return _error_response("Invalid request body.")

    content = _clean_string(payload.get("content"), "", max_length=10000)
    if not content:
        return _error_response("Message content is required.")

    with transaction.atomic():
        should_title_from_message = (
            conversation.title == NEW_CONVERSATION_TITLE
            and not AdvisorMessage.objects.filter(conversation=conversation).exists()
        )
        message = AdvisorMessage.objects.create(
            conversation=conversation,
            role=AdvisorMessage.ROLE_USER,
            content=content,
        )
        run = AdvisorRun.objects.create(conversation=conversation, user_message=message)
        if should_title_from_message:
            conversation.title = _title_from_message(content)
            conversation.save(update_fields=["title", "updated_at"])
    return JsonResponse(
        {
            "conversation": _serialize_conversation(conversation),
            "message": _serialize_message(message),
            "run": _serialize_run(run),
        },
        status=201,
    )


@login_required
@require_GET
def advisor_run_detail_view(request: HttpRequest, pk: int) -> JsonResponse:
    run = _get_user_run(_request_user(request), pk)
    return JsonResponse({"run": _serialize_run(run)})


@login_required
@require_GET
def advisor_run_events_view(request: HttpRequest, pk: int) -> StreamingHttpResponse:
    run = _get_user_run(_request_user(request), pk)
    response = StreamingHttpResponse(_stream_run_events(run.id), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@login_required
@require_POST
def advisor_run_cancel_view(request: HttpRequest, pk: int) -> JsonResponse:
    run = _get_user_run(_request_user(request), pk)
    canceled = cancel_advisor_run(run_id=run.id)
    run.refresh_from_db()
    return JsonResponse({"canceled": canceled, "run": _serialize_run(run)})


@login_required
def advisor_memory_view(request: HttpRequest) -> JsonResponse:
    user = _request_user(request)
    if request.method == "GET":
        return JsonResponse({"memory": _serialize_memory(get_advisor_memory(user))})
    if request.method == "POST":
        payload = _json_body(request)
        if payload is None:
            return _error_response("Invalid request body.")
        content = _clean_string(payload.get("content"), "", max_length=AdvisorMemory.MAX_CONTENT_LENGTH + 1)
        try:
            memory = save_advisor_memory(user, content)
        except ValidationError as exc:
            return JsonResponse({"success": False, "errors": exc.message_dict}, status=400)
        return JsonResponse({"memory": _serialize_memory(memory)})
    return _method_not_allowed(["GET", "POST"])


def _request_user(request: HttpRequest) -> UserModel:
    return cast(UserModel, request.user)


def _json_body(request: HttpRequest) -> JsonObject | None:
    try:
        body = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(body, dict):
        return cast(JsonObject, body)
    return None


def _clean_string(value: JsonValue, default: str, *, max_length: int) -> str:
    cleaned = value.strip() if isinstance(value, str) else default
    return cleaned[:max_length]


def _title_from_message(content: str) -> str:
    return (
        f"{content[:CONVERSATION_TITLE_PREFIX_LENGTH]}..." if len(content) > CONVERSATION_TITLE_MAX_LENGTH else content
    )


def _pending_runs(user: UserModel) -> list[AdvisorRun]:
    return list(
        AdvisorRun.objects.filter(
            conversation__user=user,
            status__in=[
                AdvisorRun.STATUS_PENDING,
                AdvisorRun.STATUS_RUNNING,
                AdvisorRun.STATUS_WAITING_FOR_USER,
            ],
        )
        .select_related("conversation", "user_message")
        .order_by("-created_at")
    )


def _get_user_conversation(user: UserModel, pk: int) -> AdvisorConversation:
    return get_object_or_404(AdvisorConversation, pk=pk, user=user)


def _get_user_run(user: UserModel, pk: int) -> AdvisorRun:
    return get_object_or_404(
        AdvisorRun.objects.select_related("conversation", "user_message"),
        pk=pk,
        conversation__user=user,
    )


def _serialize_conversation(conversation: AdvisorConversation) -> JsonObject:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "summary": conversation.summary,
        "is_archived": conversation.is_archived,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }


def _serialize_message(message: AdvisorMessage) -> JsonObject:
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "role": message.role,
        "content": message.content,
        "linked_run_id": message.linked_run_id,
        "created_at": message.created_at.isoformat(),
    }


def _serialize_run(run: AdvisorRun) -> JsonObject:
    return {
        "id": run.id,
        "conversation_id": run.conversation_id,
        "user_message_id": run.user_message_id,
        "status": run.status,
        "partial_markdown": run.partial_response,
        "final_markdown": run.final_response,
        "error": run.error_message,
        "follow_up_required": run.status == AdvisorRun.STATUS_WAITING_FOR_USER,
        "tool_trace": cast(JsonValue, run.tool_trace),
        "model": run.model,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
    }


def _serialize_memory(memory: AdvisorMemory) -> JsonObject:
    return {
        "content": memory.content,
        "updated_at": memory.updated_at.isoformat(),
    }


def _stream_run_events(run_id: int) -> Iterator[str]:
    last_updated_at = ""
    last_heartbeat_at = time.monotonic()
    while True:
        try:
            run = AdvisorRun.objects.select_related("conversation", "user_message").get(pk=run_id)
        except AdvisorRun.DoesNotExist:
            return
        is_terminal = run.status in TERMINAL_RUN_STATUSES
        updated_at = run.updated_at.isoformat()
        if updated_at != last_updated_at or is_terminal:
            event_name = "done" if is_terminal else "run"
            yield _sse_event(event_name, {"run": _serialize_run(run)})
            if is_terminal:
                return
            last_updated_at = updated_at
        now = time.monotonic()
        if now - last_heartbeat_at >= SSE_HEARTBEAT_SECONDS:
            yield ": heartbeat\n\n"
            last_heartbeat_at = now
        time.sleep(SSE_POLL_SECONDS)


def _sse_event(event_name: str, payload: JsonObject) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"


def _error_response(message: str) -> JsonResponse:
    return JsonResponse({"success": False, "error": message}, status=400)


def _method_not_allowed(allowed: list[str]) -> JsonResponse:
    return JsonResponse({"success": False, "error": "Method not allowed.", "allowed": allowed}, status=405)
