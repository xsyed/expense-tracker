from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.models import (
    AdvisorConversation,
    AdvisorMemory,
    AdvisorMemorySuggestion,
    AdvisorMessage,
    AdvisorRun,
)

User = get_user_model()


class AdvisorDomainModelTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="advisor@example.com")
        self.other_user = User.objects.create_user(email="other-advisor@example.com")
        self.conversation = AdvisorConversation.objects.create(
            user=self.user,
            title="Car budget",
            summary="Asked about affordability.",
        )

    def test_conversation_stores_user_owned_chat_state(self) -> None:
        self.assertEqual(self.conversation.user, self.user)
        self.assertEqual(self.conversation.title, "Car budget")
        self.assertEqual(self.conversation.summary, "Asked about affordability.")
        self.assertFalse(self.conversation.is_archived)
        self.assertIsNotNone(self.conversation.created_at)
        self.assertIsNotNone(self.conversation.updated_at)

    def test_message_roles_are_limited_and_owned_through_conversation(self) -> None:
        message = AdvisorMessage.objects.create(
            conversation=self.conversation,
            role=AdvisorMessage.ROLE_USER,
            content="Can I afford this car?",
        )
        invalid_message = AdvisorMessage(
            conversation=self.conversation,
            role="developer",
            content="Hidden prompt",
        )

        self.assertEqual(message.conversation.user, self.user)
        self.assertIn((AdvisorMessage.ROLE_USER, "User"), AdvisorMessage.ROLE_CHOICES)
        with self.assertRaises(ValidationError):
            invalid_message.full_clean()

    def test_run_statuses_are_limited_and_link_to_user_message(self) -> None:
        user_message = AdvisorMessage.objects.create(
            conversation=self.conversation,
            role=AdvisorMessage.ROLE_USER,
            content="Can I afford this car?",
        )
        run = AdvisorRun.objects.create(
            conversation=self.conversation,
            user_message=user_message,
            status=AdvisorRun.STATUS_RUNNING,
            partial_response="Checking the numbers...",
            final_response="You need current available cash first.",
            tool_trace=[{"tool": "financial_summary"}],
            model="gpt-5-mini",
        )
        invalid_run = AdvisorRun(
            conversation=self.conversation,
            user_message=user_message,
            status="waiting",
        )

        self.assertEqual(run.conversation.user, self.user)
        self.assertEqual(run.user_message, user_message)
        self.assertEqual(run.tool_trace, [{"tool": "financial_summary"}])
        self.assertIn((AdvisorRun.STATUS_COMPLETED, "Completed"), AdvisorRun.STATUS_CHOICES)
        self.assertIn((AdvisorRun.STATUS_WAITING_FOR_USER, "Waiting for user"), AdvisorRun.STATUS_CHOICES)
        with self.assertRaises(ValidationError):
            invalid_run.full_clean()

    def test_run_rejects_messages_from_another_conversation(self) -> None:
        other_conversation = AdvisorConversation.objects.create(user=self.other_user, title="Other")
        user_message = AdvisorMessage.objects.create(
            conversation=other_conversation,
            role=AdvisorMessage.ROLE_USER,
            content="Different user's question",
        )
        run = AdvisorRun(conversation=self.conversation, user_message=user_message)

        with self.assertRaises(ValidationError):
            run.full_clean()

    def test_run_rejects_non_user_message(self) -> None:
        assistant_message = AdvisorMessage.objects.create(
            conversation=self.conversation,
            role=AdvisorMessage.ROLE_ASSISTANT,
            content="Answer",
        )
        run = AdvisorRun(conversation=self.conversation, user_message=assistant_message)

        with self.assertRaises(ValidationError):
            run.full_clean()

    def test_message_linked_run_must_belong_to_same_conversation(self) -> None:
        other_conversation = AdvisorConversation.objects.create(user=self.other_user, title="Other")
        other_user_message = AdvisorMessage.objects.create(
            conversation=other_conversation,
            role=AdvisorMessage.ROLE_USER,
            content="Different question",
        )
        other_run = AdvisorRun.objects.create(conversation=other_conversation, user_message=other_user_message)
        message = AdvisorMessage(
            conversation=self.conversation,
            role=AdvisorMessage.ROLE_ASSISTANT,
            content="Answer",
            linked_run=other_run,
        )

        with self.assertRaises(ValidationError):
            message.full_clean()

    def test_memory_stores_user_approved_context_not_financial_records(self) -> None:
        memory = AdvisorMemory.objects.create(
            user=self.user,
            key="risk_tolerance",
            value="Prefers conservative cash buffers.",
            source=AdvisorMemory.SOURCE_MANUAL,
        )
        transaction_memory = AdvisorMemory(
            user=self.user,
            key="transaction_2026_06_01",
            value="Gas station 42.00",
            source=AdvisorMemory.SOURCE_MANUAL,
        )
        housing_context = AdvisorMemory(
            user=self.user,
            key="housing_context",
            value="Renting a one-bedroom apartment.",
            source=AdvisorMemory.SOURCE_MANUAL,
        )
        rent_amount = AdvisorMemory(
            user=self.user,
            key="monthly_rent",
            value="Rent is $1200 inferred from transactions.",
            source=AdvisorMemory.SOURCE_MANUAL,
        )

        self.assertEqual(memory.user, self.user)
        self.assertEqual(memory.source, AdvisorMemory.SOURCE_MANUAL)
        self.assertIn((AdvisorMemory.SOURCE_ACCEPTED_SUGGESTION, "Accepted suggestion"), AdvisorMemory.SOURCE_CHOICES)
        housing_context.full_clean()
        with self.assertRaises(ValidationError):
            transaction_memory.full_clean()
        with self.assertRaises(ValidationError):
            rent_amount.full_clean()

    def test_memory_source_choices_are_limited(self) -> None:
        memory = AdvisorMemory(
            user=self.user,
            key="payday_pattern",
            value="Paid biweekly.",
            source="imported_transaction",
        )

        with self.assertRaises(ValidationError):
            memory.full_clean()

    def test_memory_suggestion_resolution_sets_status_and_timestamp(self) -> None:
        suggestion = AdvisorMemorySuggestion.objects.create(
            user=self.user,
            conversation=self.conversation,
            key="cash_buffer_preference",
            suggested_value="Wants at least three months of expenses before large purchases.",
            rationale="User mentioned discomfort with low emergency reserves.",
        )

        suggestion.resolve(AdvisorMemorySuggestion.STATUS_ACCEPTED)
        suggestion.save()
        suggestion.refresh_from_db()

        self.assertEqual(suggestion.user, self.user)
        self.assertEqual(suggestion.conversation.user, self.user)
        self.assertEqual(suggestion.status, AdvisorMemorySuggestion.STATUS_ACCEPTED)
        self.assertIsNotNone(suggestion.resolved_at)

    def test_memory_suggestion_rejects_cross_user_conversation(self) -> None:
        suggestion = AdvisorMemorySuggestion(
            user=self.other_user,
            conversation=self.conversation,
            key="cash_buffer_preference",
            suggested_value="Wants a bigger cash buffer.",
            rationale="Said large purchases feel risky.",
        )

        with self.assertRaises(ValidationError):
            suggestion.full_clean()

    def test_memory_suggestion_resolution_requires_terminal_status(self) -> None:
        suggestion = AdvisorMemorySuggestion(
            user=self.user,
            conversation=self.conversation,
            key="cash_buffer_preference",
            suggested_value="Wants a bigger cash buffer.",
            rationale="Said large purchases feel risky.",
        )

        with self.assertRaises(ValueError):
            suggestion.resolve(AdvisorMemorySuggestion.STATUS_PENDING)
