from __future__ import annotations

import datetime
import urllib.error
from decimal import Decimal
from typing import cast
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import TestCase

from core.advisor_calculation_tools import (
    convert_currency,
    run_affordability_check,
    run_emergency_fund_calculation,
    run_large_event_plan,
)


def _payload_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    return cast(dict[str, object], payload[key])


def _payload_list(payload: dict[str, object], key: str) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], payload[key])


class AdvisorCalculationToolsTests(TestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_affordability_check_recommends_affordable_when_cash_and_surplus_cover_costs(self) -> None:
        payload = run_affordability_check(
            amount=Decimal("800.00"),
            current_available_cash=Decimal("5000.00"),
            minimum_reserve=Decimal("3000.00"),
            expected_monthly_surplus=Decimal("600.00"),
            monthly_payment=Decimal("100.00"),
        )

        self.assertEqual(payload["recommendation"], "affordable")
        self.assertEqual(payload["required_cash"], 800.0)
        self.assertEqual(payload["surplus_after_payment"], 500.0)
        self.assertEqual(payload["reserve_impact"], 1200.0)
        self.assertEqual(payload["confidence"], "high")
        self.assertEqual(payload["missing_facts"], [])

    def test_affordability_check_recommends_not_affordable_when_reserve_would_break(self) -> None:
        payload = run_affordability_check(
            amount=Decimal("2500.00"),
            current_available_cash=Decimal("4000.00"),
            minimum_reserve=Decimal("3000.00"),
            expected_monthly_surplus=Decimal("500.00"),
        )

        self.assertEqual(payload["recommendation"], "not_affordable")
        self.assertEqual(payload["reserve_impact"], -1500.0)
        self.assertEqual(payload["confidence"], "high")

    def test_affordability_check_flags_missing_current_cash_when_material(self) -> None:
        payload = run_affordability_check(
            amount=Decimal("1000.00"),
            expected_monthly_surplus=Decimal("300.00"),
            minimum_reserve=Decimal("2000.00"),
        )

        missing_facts = _payload_list(payload, "missing_facts")
        self.assertEqual(payload["recommendation"], "uncertain")
        self.assertEqual(payload["reserve_impact"], None)
        self.assertEqual(missing_facts[0]["name"], "current_available_cash")

    def test_emergency_fund_calculation_returns_target_gap_and_completion(self) -> None:
        payload = run_emergency_fund_calculation(
            monthly_essential_expenses=Decimal("2500.00"),
            required_months=Decimal("3"),
            current_emergency_savings=Decimal("1500.00"),
            savings_amount_per_period=Decimal("500.00"),
            today=datetime.date(2026, 6, 1),
        )

        self.assertEqual(payload["required_months"], 3.0)
        self.assertEqual(payload["target_fund"], 7500.0)
        self.assertEqual(payload["gap"], 6000.0)
        self.assertEqual(payload["savings_amount_per_period"], 500.0)
        self.assertEqual(payload["estimated_completion_date"], "2027-05-27")
        self.assertEqual(payload["missing_facts"], [])

    def test_emergency_fund_calculation_handles_fully_funded_result(self) -> None:
        payload = run_emergency_fund_calculation(
            monthly_essential_expenses=Decimal("2000.00"),
            required_months=Decimal("3"),
            current_emergency_savings=Decimal("7000.00"),
            savings_amount_per_period=Decimal("200.00"),
            today=datetime.date(2026, 6, 1),
        )

        self.assertEqual(payload["gap"], 0.0)
        self.assertEqual(payload["estimated_completion_date"], "2026-06-01")

    def test_emergency_fund_calculation_returns_missing_facts_without_guessing_savings(self) -> None:
        payload = run_emergency_fund_calculation(
            monthly_essential_expenses=Decimal("2500.00"),
            required_months=Decimal("3"),
        )

        missing_names = {fact["name"] for fact in _payload_list(payload, "missing_facts")}
        self.assertEqual(payload["target_fund"], 7500.0)
        self.assertEqual(payload["gap"], None)
        self.assertEqual(payload["estimated_completion_date"], None)
        self.assertEqual(missing_names, {"current_emergency_savings", "savings_amount_per_period"})

    def test_large_event_plan_returns_required_savings_and_shortfall(self) -> None:
        payload = run_large_event_plan(
            target_amount=Decimal("6000.00"),
            deadline=datetime.date(2026, 11, 28),
            current_saved_amount=Decimal("1200.00"),
            planned_savings_per_month=Decimal("600.00"),
            today=datetime.date(2026, 6, 1),
        )

        alternatives = _payload_list(payload, "alternatives")
        self.assertEqual(payload["monthly_savings_required"], 800.0)
        self.assertEqual(payload["paycheck_savings_required"], 400.0)
        self.assertEqual(payload["likely_shortfall"], 1200.0)
        self.assertEqual(alternatives[0], {"type": "increase_monthly_savings", "amount": 800.0})

    def test_large_event_plan_handles_already_funded_result(self) -> None:
        payload = run_large_event_plan(
            target_amount=Decimal("3000.00"),
            deadline=datetime.date(2026, 12, 1),
            current_saved_amount=Decimal("3500.00"),
            planned_savings_per_month=Decimal("0.00"),
            today=datetime.date(2026, 6, 1),
        )

        self.assertEqual(payload["monthly_savings_required"], 0.0)
        self.assertEqual(payload["paycheck_savings_required"], 0.0)
        self.assertEqual(payload["likely_shortfall"], 0.0)
        self.assertEqual(payload["alternatives"], [])

    def test_large_event_plan_returns_missing_facts_without_guessing_deadline_or_saved_amount(self) -> None:
        payload = run_large_event_plan(target_amount=Decimal("4000.00"), deadline=None)

        missing_names = {fact["name"] for fact in _payload_list(payload, "missing_facts")}
        self.assertEqual(payload["deadline"], None)
        self.assertEqual(payload["current_saved_amount"], None)
        self.assertEqual(payload["monthly_savings_required"], None)
        self.assertEqual(missing_names, {"deadline", "current_saved_amount"})

    @patch("core.advisor_calculation_tools.urllib.request.urlopen")
    def test_convert_currency_uses_frankfurter_rate_and_caches_provider_metadata(self, mock_urlopen: Mock) -> None:
        response = Mock()
        response.read.return_value = b'{"amount":1.0,"base":"USD","date":"2026-06-26","rates":{"CAD":1.37}}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = response

        first = convert_currency(amount=Decimal("100.00"), source_currency="usd", target_currency="cad")
        second = convert_currency(amount=Decimal("100.00"), source_currency="USD", target_currency="CAD")

        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["converted_amount"], 137.0)
        self.assertEqual(first["rate_date"], "2026-06-26")
        self.assertEqual(_payload_dict(first, "provider")["name"], "Frankfurter")
        self.assertFalse(_payload_dict(first, "provider")["cached"])
        self.assertTrue(_payload_dict(second, "provider")["cached"])
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("core.advisor_calculation_tools.urllib.request.urlopen")
    def test_convert_currency_returns_failure_payload_when_rate_fetch_fails(self, mock_urlopen: Mock) -> None:
        mock_urlopen.side_effect = urllib.error.URLError("rate service unavailable")

        payload = convert_currency(amount=Decimal("100.00"), source_currency="USD", target_currency="CAD")

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["converted_amount"], None)
        self.assertIn("rate service unavailable", str(payload["error"]))
        self.assertEqual(_payload_dict(payload, "provider")["name"], "Frankfurter")

    def test_convert_currency_handles_same_currency_without_network_call(self) -> None:
        payload = convert_currency(amount=Decimal("42.50"), source_currency="cad", target_currency="CAD")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["converted_amount"], 42.5)
        self.assertEqual(payload["rate"], 1.0)
