from __future__ import annotations

from .models import AdvisorMemory
from .models import User as UserModel


def get_advisor_memory(user: UserModel) -> AdvisorMemory:
    memory, _created = AdvisorMemory.objects.get_or_create(user=user, defaults={"content": ""})
    return memory


def save_advisor_memory(user: UserModel, content: str) -> AdvisorMemory:
    memory = AdvisorMemory.objects.filter(user=user).first()
    if memory is None:
        memory = AdvisorMemory(user=user)
    memory.content = content.strip()
    memory.full_clean()
    if memory.pk:
        memory.save(update_fields=["content", "updated_at"])
    else:
        memory.save()
    return memory
