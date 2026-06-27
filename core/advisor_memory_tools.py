from __future__ import annotations

from .models import AdvisorConversation, AdvisorMemorySuggestion
from .models import User as UserModel


def create_memory_suggestion(
    user: UserModel,
    *,
    conversation: AdvisorConversation,
    key: str,
    suggested_value: str,
    rationale: str,
) -> dict[str, object]:
    suggestion = AdvisorMemorySuggestion(
        user=user,
        conversation=conversation,
        key=key,
        suggested_value=suggested_value,
        rationale=rationale,
        status=AdvisorMemorySuggestion.STATUS_PENDING,
    )
    suggestion.full_clean()
    suggestion.save()
    return {
        "id": suggestion.id,
        "key": suggestion.key,
        "suggested_value": suggestion.suggested_value,
        "rationale": suggestion.rationale,
        "status": suggestion.status,
        "active": False,
    }
