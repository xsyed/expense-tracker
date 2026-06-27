from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .advisor_memory_policy import advisor_memory_policy_error


class AdvisorConversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="advisor_conversations",
    )
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.title


class AdvisorMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_SYSTEM = "system"
    ROLE_CHOICES = [
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
        (ROLE_SYSTEM, "System"),
    ]

    conversation = models.ForeignKey(
        AdvisorConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=9, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    linked_run = models.ForeignKey(
        "AdvisorRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:50]}"

    def clean(self) -> None:
        super().clean()
        linked_run = self.linked_run
        if linked_run is not None and linked_run.conversation_id != self.conversation_id:
            raise ValidationError({"linked_run": "Linked run must belong to the same conversation."})


class AdvisorRun(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_WAITING_FOR_USER = "waiting_for_user"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_WAITING_FOR_USER, "Waiting for user"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELED, "Canceled"),
    ]

    conversation = models.ForeignKey(
        AdvisorConversation,
        on_delete=models.CASCADE,
        related_name="runs",
    )
    user_message = models.ForeignKey(
        AdvisorMessage,
        on_delete=models.CASCADE,
        related_name="runs",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    partial_response = models.TextField(blank=True)
    final_response = models.TextField(blank=True)
    tool_trace = models.JSONField(default=list, blank=True)
    model = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.conversation}: {self.status}"

    def clean(self) -> None:
        super().clean()
        errors = {}
        if self.user_message_id and self.user_message.conversation_id != self.conversation_id:
            errors["user_message"] = "User message must belong to the same conversation."
        if self.user_message_id and self.user_message.role != AdvisorMessage.ROLE_USER:
            errors["user_message"] = "Advisor Run must be linked to a user message."
        if errors:
            raise ValidationError(errors)


class AdvisorMemory(models.Model):
    SOURCE_MANUAL = "manual"
    SOURCE_ACCEPTED_SUGGESTION = "accepted_suggestion"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_ACCEPTED_SUGGESTION, "Accepted suggestion"),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="advisor_memories",
    )
    key = models.CharField(max_length=100)
    value = models.TextField()
    source = models.CharField(max_length=19, choices=SOURCE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]
        unique_together = ("user", "key")
        verbose_name = "advisor memory"
        verbose_name_plural = "advisor memories"

    def __str__(self) -> str:
        return self.key

    def clean(self) -> None:
        super().clean()
        policy_error = advisor_memory_policy_error(key=self.key, value=self.value)
        if policy_error:
            raise ValidationError({"key": policy_error})


class AdvisorMemorySuggestion(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_DISMISSED = "dismissed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_DISMISSED, "Dismissed"),
    ]
    RESOLVED_STATUSES = {STATUS_ACCEPTED, STATUS_REJECTED, STATUS_DISMISSED}

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="advisor_memory_suggestions",
    )
    conversation = models.ForeignKey(
        AdvisorConversation,
        on_delete=models.CASCADE,
        related_name="memory_suggestions",
    )
    key = models.CharField(max_length=100)
    suggested_value = models.TextField()
    rationale = models.TextField()
    status = models.CharField(max_length=9, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.key

    def clean(self) -> None:
        super().clean()
        policy_error = advisor_memory_policy_error(
            key=self.key,
            value=self.suggested_value,
            rationale=self.rationale,
        )
        if policy_error:
            raise ValidationError({"suggested_value": policy_error})
        if self.conversation_id and self.user_id != self.conversation.user_id:
            raise ValidationError({"conversation": "Memory suggestion user must own the conversation."})

    def resolve(self, status: str) -> None:
        if status not in self.RESOLVED_STATUSES:
            raise ValueError("Memory suggestion must resolve to accepted, rejected, or dismissed.")
        self.status = status
        self.resolved_at = timezone.now()
