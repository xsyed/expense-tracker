from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

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
    MAX_CONTENT_LENGTH = 3000

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="advisor_memory",
    )
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__email"]
        verbose_name = "advisor memory"
        verbose_name_plural = "advisor memories"

    def __str__(self) -> str:
        return f"Advisor memory for {self.user}"

    def clean(self) -> None:
        super().clean()
        if len(self.content) > self.MAX_CONTENT_LENGTH:
            raise ValidationError({"content": f"Advisor Memory must be {self.MAX_CONTENT_LENGTH} characters or less."})
        policy_error = advisor_memory_policy_error(content=self.content)
        if policy_error:
            raise ValidationError({"content": policy_error})
