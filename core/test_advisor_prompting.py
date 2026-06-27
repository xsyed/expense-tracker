from __future__ import annotations

import datetime
import json
import urllib.error
from decimal import Decimal
from email.message import Message
from typing import ClassVar
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from core.advisor_models import AdvisorConversation, AdvisorMessage
from core.advisor_prompting import (
    PlannerContractError,
    ToolOutput,
    build_advisor_messages,
    build_planner_messages,
    generate_advisor_answer,
    plan_advisor_tools,
    requires_follow_up_gate,
)
from core.advisor_provider import OpenRouterClient, OpenRouterError, OpenRouterMessage, OpenRouterResponse
from core.models import Account, Category, ExpenseMonth, Transaction

User = get_user_model()


class FakeOpenRouterClient(OpenRouterClient):
    def __init__(self, response: OpenRouterResponse) -> None:
        self.response = response
        self.called = False

    def chat_completion(
        self,
        *,
        model: str,
        messages: list[OpenRouterMessage],
        temperature: float = 0.2,
    ) -> OpenRouterResponse:
        self.called = True
        return self.response


@override_settings(OPENROUTER_API_KEY="configured", ADVISOR_MODEL="answer-model", ADVISOR_PLANNER_MODEL="planner-model")
class AdvisorPromptingTests(TestCase):
    today: ClassVar[datetime.date] = datetime.date(2026, 6, 15)

    def setUp(self) -> None:
        self.user = User.objects.create_user(email="prompting@example.com")
        self.conversation = AdvisorConversation.objects.create(
            user=self.user,
            title="Car budget",
            summary="User asked about a possible vehicle purchase.",
        )
        AdvisorMessage.objects.create(
            conversation=self.conversation,
            role=AdvisorMessage.ROLE_USER,
            content="Earlier short question",
        )
        AdvisorMessage.objects.create(
            conversation=self.conversation,
            role=AdvisorMessage.ROLE_ASSISTANT,
            content="Earlier short answer",
        )
        self.current_message = AdvisorMessage.objects.create(
            conversation=self.conversation,
            role=AdvisorMessage.ROLE_USER,
            content="Can I afford this vehicle?",
        )

    def test_prompt_assembly_excludes_raw_full_transaction_history_by_default(self) -> None:
        account = Account.objects.create(user=self.user, name="Chequing")
        category = Category.objects.create(user=self.user, name="Auto", category_type="expense")
        month = ExpenseMonth.objects.create(user=self.user, month=datetime.date(2026, 6, 1))
        Transaction.objects.create(
            expense_month=month,
            account=account,
            category=category,
            description="Dealer raw transaction that should stay private",
            amount=Decimal("3210.00"),
            date=self.today,
            transaction_type="expense",
        )

        messages = build_advisor_messages(
            conversation=self.conversation,
            current_user_message=self.current_message,
            tool_outputs=[],
        )
        joined_content = "\n".join(message["content"] for message in messages)

        self.assertIn("Approved Advisor Memory", messages[1]["content"])
        self.assertIn("Compact Conversation Summary", messages[2]["content"])
        self.assertIn("Current User Message", messages[-3]["content"])
        self.assertIn("Selected Tool Outputs", messages[-2]["content"])
        self.assertNotIn("Dealer raw transaction that should stay private", joined_content)

    def test_planner_prompt_includes_tool_schemas_and_current_date(self) -> None:
        messages = build_planner_messages("Use app data for a starter budget.", today=self.today)
        joined_content = "\n".join(message["content"] for message in messages)

        self.assertIn('get_budget_position: {"month": "YYYY-MM-DD"}', joined_content)
        self.assertIn("When the user asks to use app data", joined_content)
        self.assertIn("Current Date:\n2026-06-15", joined_content)

    @patch("core.advisor_provider.urllib.request.urlopen")
    def test_openrouter_client_returns_successful_assistant_message(self, mock_urlopen: Mock) -> None:
        response = Mock()
        response.read.return_value = json.dumps(
            {
                "model": "answer-model",
                "choices": [{"message": {"role": "assistant", "content": "## Direct answer\nNo."}}],
            }
        ).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = response
        client = OpenRouterClient(api_key="configured")

        result = client.chat_completion(model="answer-model", messages=[{"role": "user", "content": "Hi"}])

        self.assertEqual(result.content, "## Direct answer\nNo.")
        self.assertEqual(result.model, "answer-model")

    @patch("core.advisor_provider.urllib.request.urlopen")
    def test_openrouter_client_raises_provider_error_for_model_failure(self, mock_urlopen: Mock) -> None:
        error = urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=400,
            msg="Bad Request",
            hdrs=Message(),
            fp=Mock(read=Mock(return_value=b'{"error":"model unavailable"}')),
        )
        mock_urlopen.side_effect = error
        client = OpenRouterClient(api_key="configured")

        with self.assertRaises(OpenRouterError) as context:
            client.chat_completion(model="answer-model", messages=[{"role": "user", "content": "Hi"}])

        self.assertIn("model unavailable", str(context.exception))

    @patch("core.advisor_provider.urllib.request.urlopen")
    def test_planner_contract_accepts_approved_tools_from_openrouter_response(self, mock_urlopen: Mock) -> None:
        content = json.dumps(
            {
                "tool_calls": [
                    {"name": "get_budget_position", "arguments": {"month": "2026-06-01"}},
                    {"name": "run_affordability_check", "arguments": {"amount": 1200}},
                ]
            }
        )
        response = Mock()
        response.read.return_value = json.dumps(
            {"model": "planner-model", "choices": [{"message": {"role": "assistant", "content": content}}]}
        ).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = response
        client = OpenRouterClient(api_key="configured")

        tool_calls = plan_advisor_tools(client=client, user_message="Can I afford a car?")

        self.assertEqual(
            [tool_call["name"] for tool_call in tool_calls],
            ["get_budget_position", "run_affordability_check"],
        )

    @patch("core.advisor_provider.urllib.request.urlopen")
    def test_planner_contract_rejects_unapproved_tools(self, mock_urlopen: Mock) -> None:
        content = json.dumps({"tool_calls": [{"name": "web_search", "arguments": {"query": "rates"}}]})
        response = Mock()
        response.read.return_value = json.dumps(
            {"model": "planner-model", "choices": [{"message": {"role": "assistant", "content": content}}]}
        ).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = response
        client = OpenRouterClient(api_key="configured")

        with self.assertRaises(PlannerContractError):
            plan_advisor_tools(client=client, user_message="Search the web for rates")

    def test_follow_up_gate_prevents_model_call_for_high_impact_missing_facts(self) -> None:
        tool_outputs: list[ToolOutput] = [
            {
                "name": "run_affordability_check",
                "output": {
                    "recommendation": "uncertain",
                    "missing_facts": [
                        {
                            "name": "current_available_cash",
                            "reason": "Needed for reserve impact.",
                            "impact": "Could change the decision.",
                        }
                    ],
                },
            }
        ]
        client = FakeOpenRouterClient(OpenRouterResponse(content="Should not be used", model="answer-model", raw={}))

        answer = generate_advisor_answer(
            client=client,
            conversation=self.conversation,
            current_user_message=self.current_message,
            tool_outputs=tool_outputs,
        )

        self.assertTrue(requires_follow_up_gate(self.current_message.content, tool_outputs))
        self.assertTrue(answer.follow_up_required)
        self.assertFalse(client.called)
        self.assertIn("current_available_cash", answer.content)
        self.assertIn("Low until these facts are known", answer.content)

    def test_answer_generation_uses_openrouter_when_follow_up_gate_is_clear(self) -> None:
        tool_outputs: list[ToolOutput] = [
            {
                "name": "run_affordability_check",
                "output": {"recommendation": "not_affordable", "missing_facts": []},
            }
        ]
        client = FakeOpenRouterClient(OpenRouterResponse(content="Direct answer: no.", model="answer-model", raw={}))

        answer = generate_advisor_answer(
            client=client,
            conversation=self.conversation,
            current_user_message=self.current_message,
            tool_outputs=tool_outputs,
        )

        self.assertTrue(client.called)
        self.assertFalse(answer.follow_up_required)
        self.assertEqual(answer.content, "Direct answer: no.")
