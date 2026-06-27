from __future__ import annotations

import re

from django.core.exceptions import ValidationError

from .advisor_memory_tools import create_memory_suggestion
from .advisor_prompting import AdvisorAnswer
from .models import AdvisorMessage, AdvisorRun

MEMORY_APPROVAL_MODEL = "memory-approval"
MEMORY_APPROVAL_KEY = "profile_context"

_APPROVAL_PHRASES = frozenset(
    {
        "approve these",
        "approve them",
        "save memory suggestions",
        "save suggested memory",
        "save suggestions",
        "save the memory suggestions",
        "save these",
        "save these memory suggestions",
        "save them",
        "save this",
        "save those",
        "yes save these",
        "yes save them",
    }
)
_STOP_PREFIXES = (
    "i would avoid",
    "i would not",
    "next actions",
    "reply with",
)
_SKIP_PREFIXES = (
    "if you want",
    "i suggest",
    "section",
)
_CANDIDATE_MARKERS = (
    "better memory items to save",
    "better memory set to save",
    "save only stable",
    "recommend saving",
    "recommended memory",
    "suggest these exact entries",
)
_FALLBACK_HEADINGS = (
    "memory suggestions",
    "save now",
)


def maybe_create_memory_approval_answer(run: AdvisorRun) -> AdvisorAnswer | None:
    if not _is_memory_approval_request(run.user_message.content):
        return None

    assistant_message = _latest_assistant_message(run)
    if assistant_message is None:
        return _missing_suggestion_answer()

    suggested_value = _extract_memory_suggestion_value(assistant_message.content)
    if not suggested_value:
        return _missing_suggestion_answer()

    try:
        create_memory_suggestion(
            run.conversation.user,
            conversation=run.conversation,
            key=MEMORY_APPROVAL_KEY,
            suggested_value=suggested_value,
            rationale="User approved the previous assistant memory suggestions.",
        )
    except ValidationError:
        return AdvisorAnswer(
            content=(
                "I could not save those memory suggestions because they include details that do not pass the "
                "advisor memory policy.\n\n"
                "## Next actions\n"
                "Edit the memory suggestion down to stable preferences or profile context, then try again."
            ),
            model=MEMORY_APPROVAL_MODEL,
        )

    return AdvisorAnswer(
        content=(
            "Saved these as a pending memory suggestion.\n\n"
            "## Next actions\n"
            "Open the Memory tab and accept `profile_context` to make it durable advisor memory."
        ),
        model=MEMORY_APPROVAL_MODEL,
    )


def _is_memory_approval_request(content: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", content.lower()).strip()
    return normalized in _APPROVAL_PHRASES or _references_prior_memory_save(normalized)


def _references_prior_memory_save(normalized: str) -> bool:
    save_terms = ("approve", "remember", "save", "store")
    memory_terms = ("context", "memory", "preference", "preferences")
    prior_terms = ("above", "earlier", "last", "previous", "prior", "recommended", "suggested")
    return (
        any(term in normalized.split() for term in save_terms)
        and any(term in normalized for term in memory_terms)
        and any(term in normalized for term in prior_terms)
    )


def _latest_assistant_message(run: AdvisorRun) -> AdvisorMessage | None:
    return (
        AdvisorMessage.objects.filter(conversation=run.conversation, role=AdvisorMessage.ROLE_ASSISTANT)
        .order_by("-created_at", "-pk")
        .first()
    )


def _extract_memory_suggestion_value(markdown: str) -> str:
    lines = [line.strip() for line in markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    start_index = _candidate_start_index(lines)
    if start_index is None:
        return ""

    items: list[str] = []
    saw_list_item = False
    for raw_line in lines[start_index:]:
        is_list_item = _is_list_item(raw_line)
        cleaned = _clean_memory_line(raw_line)
        if not cleaned:
            if items:
                continue
            continue
        normalized = cleaned.lower().rstrip(":")
        if any(normalized.startswith(prefix) for prefix in _STOP_PREFIXES):
            break
        if _is_heading(raw_line) and items:
            break
        if items and saw_list_item and not is_list_item:
            break
        if any(normalized.startswith(prefix) for prefix in _SKIP_PREFIXES):
            continue
        items.append(cleaned)
        saw_list_item = saw_list_item or is_list_item

    return "\n".join(items).strip()[:10000]


def _candidate_start_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if any(marker in line.lower() for marker in _CANDIDATE_MARKERS):
            return index + 1
    for index, line in enumerate(lines):
        if _heading_text(line).lower() in _FALLBACK_HEADINGS:
            return index + 1
    return None


def _clean_memory_line(line: str) -> str:
    cleaned = re.sub(r"^#{1,6}\s*", "", line).strip()
    cleaned = re.sub(r"^(?:[-*]|\d+[.)])\s+", "", cleaned).strip()
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    return cleaned.strip()


def _is_list_item(line: str) -> bool:
    return bool(re.match(r"^(?:[-*]|\d+[.)])\s+\S", line.strip()))


def _is_heading(line: str) -> bool:
    return bool(re.match(r"^#{1,6}\s+\S", line))


def _heading_text(line: str) -> str:
    return _clean_memory_line(line).rstrip(":")


def _missing_suggestion_answer() -> AdvisorAnswer:
    return AdvisorAnswer(
        content=(
            "I could not find prior memory suggestions to save.\n\n"
            "## Next actions\n"
            "Ask for memory suggestions first, then reply `save these` after I list them."
        ),
        model=MEMORY_APPROVAL_MODEL,
    )
