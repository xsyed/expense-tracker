from __future__ import annotations

import datetime
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from core.advisor_prompting import AdvisorAnswer
from core.advisor_worker import cancel_advisor_run, mark_stale_running_runs, process_next_advisor_run
from core.models import AdvisorConversation, AdvisorMessage, AdvisorRun

User = get_user_model()


@override_settings(OPENROUTER_API_KEY="configured", ADVISOR_MODEL="answer-model", ADVISOR_PLANNER_MODEL="planner-model")
class AdvisorWorkerTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="worker@example.com")
        self.conversation = AdvisorConversation.objects.create(user=self.user, title="Worker test")
        self.user_message = AdvisorMessage.objects.create(
            conversation=self.conversation,
            role=AdvisorMessage.ROLE_USER,
            content="Can I afford this vehicle?",
        )

    def _create_run(self, status: str = AdvisorRun.STATUS_PENDING) -> AdvisorRun:
        return AdvisorRun.objects.create(
            conversation=self.conversation,
            user_message=self.user_message,
            status=status,
        )

    @patch("core.advisor_worker.generate_advisor_answer")
    @patch("core.advisor_worker.plan_advisor_tools")
    def test_worker_processes_pending_run_to_completed_message(
        self,
        mock_plan: Mock,
        mock_answer: Mock,
    ) -> None:
        run = self._create_run()
        mock_plan.return_value = [{"name": "get_user_profile_memory", "arguments": {}}]
        mock_answer.return_value = AdvisorAnswer(content="Direct answer: no.", model="answer-model")

        processed = process_next_advisor_run()

        run.refresh_from_db()
        self.assertTrue(processed)
        self.assertEqual(run.status, AdvisorRun.STATUS_COMPLETED)
        self.assertEqual(run.partial_response, "Drafting advisor response...")
        self.assertEqual(run.final_response, "Direct answer: no.")
        self.assertEqual(run.model, "answer-model")
        self.assertEqual(
            run.tool_trace,
            [
                {
                    "name": "get_user_profile_memory",
                    "status": "completed",
                    "argument_keys": [],
                    "output_keys": ["capped", "count", "items"],
                }
            ],
        )
        assistant_message = AdvisorMessage.objects.get(role=AdvisorMessage.ROLE_ASSISTANT)
        self.assertEqual(assistant_message.content, "Direct answer: no.")
        self.assertEqual(assistant_message.linked_run, run)

    @patch("core.advisor_worker.plan_advisor_tools", side_effect=RuntimeError("planner unavailable"))
    def test_worker_marks_run_failed_on_exception(self, _mock_plan: Mock) -> None:
        run = self._create_run()

        processed = process_next_advisor_run()

        run.refresh_from_db()
        self.assertTrue(processed)
        self.assertEqual(run.status, AdvisorRun.STATUS_FAILED)
        self.assertIn("planner unavailable", run.error_message)
        self.assertFalse(AdvisorMessage.objects.filter(role=AdvisorMessage.ROLE_ASSISTANT).exists())

    def test_stale_running_runs_are_marked_failed(self) -> None:
        run = self._create_run(status=AdvisorRun.STATUS_RUNNING)
        stale_timestamp = timezone.now() - datetime.timedelta(minutes=30)
        AdvisorRun.objects.filter(pk=run.pk).update(updated_at=stale_timestamp)

        count = mark_stale_running_runs(stale_after=datetime.timedelta(minutes=15))

        run.refresh_from_db()
        self.assertEqual(count, 1)
        self.assertEqual(run.status, AdvisorRun.STATUS_FAILED)
        self.assertIn("worker stopped", run.error_message)

    def test_pending_run_can_be_canceled_before_claim(self) -> None:
        run = self._create_run()

        canceled = cancel_advisor_run(run_id=run.id)
        processed = process_next_advisor_run()

        run.refresh_from_db()
        self.assertTrue(canceled)
        self.assertFalse(processed)
        self.assertEqual(run.status, AdvisorRun.STATUS_CANCELED)
        self.assertFalse(AdvisorMessage.objects.filter(role=AdvisorMessage.ROLE_ASSISTANT).exists())

    @patch("core.advisor_worker.plan_advisor_tools")
    def test_running_run_cancellation_does_not_create_assistant_message(self, mock_plan: Mock) -> None:
        run = self._create_run()

        def cancel_during_plan(*, client: object, user_message: str) -> list[dict[str, object]]:
            cancel_advisor_run(run_id=run.id)
            return []

        mock_plan.side_effect = cancel_during_plan

        processed = process_next_advisor_run()

        run.refresh_from_db()
        self.assertTrue(processed)
        self.assertEqual(run.status, AdvisorRun.STATUS_CANCELED)
        self.assertFalse(AdvisorMessage.objects.filter(role=AdvisorMessage.ROLE_ASSISTANT).exists())

    @patch("core.advisor_worker.plan_advisor_tools")
    def test_follow_up_gate_stores_waiting_for_user_state(self, mock_plan: Mock) -> None:
        run = self._create_run()
        mock_plan.return_value = [{"name": "run_affordability_check", "arguments": {"amount": 1200}}]

        processed = process_next_advisor_run()

        run.refresh_from_db()
        self.assertTrue(processed)
        self.assertEqual(run.status, AdvisorRun.STATUS_WAITING_FOR_USER)
        self.assertIn("current_available_cash", run.final_response)
        self.assertEqual(run.model, "follow-up-gate")
        self.assertFalse(AdvisorMessage.objects.filter(role=AdvisorMessage.ROLE_ASSISTANT).exists())

    def test_management_command_can_run_once_without_pending_work(self) -> None:
        call_command("process_advisor_runs", "--once")
