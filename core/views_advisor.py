from __future__ import annotations

import json
from typing import Union, cast

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from .advisor_memory import get_advisor_memory, save_advisor_memory
from .advisor_worker import cancel_advisor_run
from .models import AdvisorConversation, AdvisorMemory, AdvisorMessage, AdvisorRun
from .models import User as UserModel

JsonValue = Union[None, bool, int, float, str, list["JsonValue"], dict[str, "JsonValue"]]
JsonObject = dict[str, JsonValue]

RECENT_CONVERSATION_LIMIT = 10


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
        title = _clean_string(payload.get("title"), "New conversation", max_length=200)
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
        message = AdvisorMessage.objects.create(
            conversation=conversation,
            role=AdvisorMessage.ROLE_USER,
            content=content,
        )
        run = AdvisorRun.objects.create(conversation=conversation, user_message=message)
    return JsonResponse({"message": _serialize_message(message), "run": _serialize_run(run)}, status=201)


@login_required
@require_GET
def advisor_run_detail_view(request: HttpRequest, pk: int) -> JsonResponse:
    run = _get_user_run(_request_user(request), pk)
    return JsonResponse({"run": _serialize_run(run)})


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


def _error_response(message: str) -> JsonResponse:
    return JsonResponse({"success": False, "error": message}, status=400)


def _method_not_allowed(allowed: list[str]) -> JsonResponse:
    return JsonResponse({"success": False, "error": "Method not allowed.", "allowed": allowed}, status=405)
