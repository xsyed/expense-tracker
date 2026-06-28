from __future__ import annotations

import json
from typing import Protocol, cast

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import AdvisorConversation, AdvisorMemory, AdvisorMessage, AdvisorRun

User = get_user_model()


class JsonTestResponse(Protocol):
    status_code: int

    def json(self) -> dict[str, object]: ...


class AdvisorApiTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="advisor-api@example.com")
        self.other_user = User.objects.create_user(email="advisor-api-other@example.com")
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        TOTPDevice.objects.create(user=self.other_user, name="default", confirmed=True)
        self.client.force_login(self.user)
        self.conversation = AdvisorConversation.objects.create(user=self.user, title="Main chat")
        self.user_message = AdvisorMessage.objects.create(
            conversation=self.conversation,
            role=AdvisorMessage.ROLE_USER,
            content="Can I buy a bike?",
        )
        self.advisor_run = AdvisorRun.objects.create(
            conversation=self.conversation,
            user_message=self.user_message,
            status=AdvisorRun.STATUS_RUNNING,
            partial_response="Drafting...",
        )

    def _post_json(self, url_name: str, payload: dict[str, object], **kwargs: int) -> JsonTestResponse:
        return cast(
            JsonTestResponse,
            self.client.post(
                reverse(url_name, kwargs=kwargs),
                data=json.dumps(payload),
                content_type="application/json",
            ),
        )

    def test_bootstrap_requires_authentication(self) -> None:
        self.client.logout()

        response = self.client.get(reverse("advisor_bootstrap"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("two_factor:login"), response["Location"])

    def test_mutating_endpoint_requires_csrf_token(self) -> None:
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.post(
            reverse("advisor_conversations"),
            data=json.dumps({"title": "CSRF check"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_bootstrap_returns_active_conversation_runs_and_memory_document(self) -> None:
        memory = AdvisorMemory.objects.create(
            user=self.user,
            content="Conservative risk preference.",
        )

        response = self.client.get(reverse("advisor_bootstrap"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["active_conversation"]["id"], self.conversation.id)
        self.assertEqual(payload["recent_conversations"][0]["id"], self.conversation.id)
        self.assertEqual(payload["pending_runs"][0]["id"], self.advisor_run.id)
        self.assertEqual(payload["memory"]["content"], memory.content)
        self.assertEqual(payload["memory"]["updated_at"], memory.updated_at.isoformat())
        self.assertNotIn("pending_memory_suggestions", payload)

    def test_conversation_list_and_create_are_user_scoped(self) -> None:
        AdvisorConversation.objects.create(user=self.other_user, title="Other chat")

        list_response = self.client.get(reverse("advisor_conversations"))
        create_response = self._post_json("advisor_conversations", {"title": "New plan"})

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual([item["id"] for item in list_response.json()["conversations"]], [self.conversation.id])
        self.assertEqual(create_response.status_code, 201)
        created_conversation = cast(dict[str, object], create_response.json()["conversation"])
        self.assertEqual(created_conversation["title"], "New plan")
        self.assertTrue(AdvisorConversation.objects.filter(user=self.user, title="New plan").exists())

    def test_conversation_detail_returns_messages_and_runs(self) -> None:
        response = self.client.get(reverse("advisor_conversation_detail", kwargs={"pk": self.conversation.id}))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["conversation"]["id"], self.conversation.id)
        self.assertEqual(payload["messages"][0]["id"], self.user_message.id)
        self.assertEqual(payload["runs"][0]["id"], self.advisor_run.id)

    def test_message_create_creates_user_message_and_pending_run(self) -> None:
        response = self._post_json(
            "advisor_message_create",
            {"content": "Should I increase savings?"},
            pk=self.conversation.id,
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        message_payload = cast(dict[str, object], payload["message"])
        run_payload = cast(dict[str, object], payload["run"])
        message = AdvisorMessage.objects.get(pk=cast(int, message_payload["id"]))
        run = AdvisorRun.objects.get(pk=cast(int, run_payload["id"]))
        self.assertEqual(message.role, AdvisorMessage.ROLE_USER)
        self.assertEqual(message.content, "Should I increase savings?")
        self.assertEqual(run.status, AdvisorRun.STATUS_PENDING)
        self.assertEqual(run.user_message, message)

    def test_run_poll_and_cancel_are_user_scoped(self) -> None:
        poll_response = self.client.get(reverse("advisor_run_detail", kwargs={"pk": self.advisor_run.id}))
        cancel_response = self.client.post(reverse("advisor_run_cancel", kwargs={"pk": self.advisor_run.id}))

        self.assertEqual(poll_response.status_code, 200)
        self.assertEqual(poll_response.json()["run"]["partial_markdown"], "Drafting...")
        self.assertFalse(poll_response.json()["run"]["follow_up_required"])
        self.assertEqual(cancel_response.status_code, 200)
        self.advisor_run.refresh_from_db()
        self.assertEqual(self.advisor_run.status, AdvisorRun.STATUS_CANCELED)
        self.assertTrue(cancel_response.json()["canceled"])

    def test_waiting_run_poll_sets_follow_up_required(self) -> None:
        AdvisorRun.objects.filter(pk=self.advisor_run.pk).update(
            status=AdvisorRun.STATUS_WAITING_FOR_USER,
            final_response="Need current cash balance.",
        )

        response = self.client.get(reverse("advisor_run_detail", kwargs={"pk": self.advisor_run.id}))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["run"]["follow_up_required"])
        self.assertEqual(response.json()["run"]["final_markdown"], "Need current cash balance.")

    def test_memory_get_and_post_save_document(self) -> None:
        create_response = self._post_json(
            "advisor_memory",
            {"content": "Keep one month in chequing."},
        )
        update_response = self._post_json(
            "advisor_memory",
            {"content": "Keep two months in chequing."},
        )
        memory = AdvisorMemory.objects.get(user=self.user)
        list_response = self.client.get(reverse("advisor_memory"))

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(memory.content, "Keep two months in chequing.")
        self.assertEqual(list_response.json()["memory"]["content"], memory.content)

    def test_memory_rejects_financial_record_content(self) -> None:
        response = self._post_json("advisor_memory", {"content": "Transaction summary: do not store this."})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(AdvisorMemory.objects.filter(user=self.user).exists())

    def test_memory_rejects_transaction_derived_context_without_deleting_existing(self) -> None:
        memory = AdvisorMemory.objects.create(
            user=self.user,
            content="Keep one month in chequing.",
        )

        response = self._post_json(
            "advisor_memory",
            {"content": "Monthly salary is $5000 inferred from transactions."},
        )

        self.assertEqual(response.status_code, 400)
        memory.refresh_from_db()
        self.assertEqual(memory.content, "Keep one month in chequing.")

    def test_other_user_records_return_not_found_for_reads_and_mutations(self) -> None:
        other_conversation = AdvisorConversation.objects.create(user=self.other_user, title="Other")
        other_message = AdvisorMessage.objects.create(
            conversation=other_conversation,
            role=AdvisorMessage.ROLE_USER,
            content="Other message",
        )
        other_run = AdvisorRun.objects.create(conversation=other_conversation, user_message=other_message)
        other_memory = AdvisorMemory.objects.create(user=self.other_user, content="Private")

        responses = [
            self.client.get(reverse("advisor_conversation_detail", kwargs={"pk": other_conversation.id})),
            self._post_json("advisor_message_create", {"content": "Cross-user"}, pk=other_conversation.id),
            self.client.get(reverse("advisor_run_detail", kwargs={"pk": other_run.id})),
            self.client.post(reverse("advisor_run_cancel", kwargs={"pk": other_run.id})),
        ]

        self.assertEqual([response.status_code for response in responses], [404, 404, 404, 404])
        self.assertTrue(AdvisorRun.objects.filter(pk=other_run.id, status=AdvisorRun.STATUS_PENDING).exists())
        self.assertEqual(self.client.get(reverse("advisor_memory")).json()["memory"]["content"], "")
        self.assertTrue(AdvisorMemory.objects.filter(pk=other_memory.id, content="Private").exists())
