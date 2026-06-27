from __future__ import annotations

import datetime
from decimal import Decimal
from typing import ClassVar, cast

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.advisor_memory_tools import create_memory_suggestion
from core.advisor_tools import (
    get_budget_position,
    get_cash_flow_summary,
    get_goal_status,
    get_recent_spending_brief,
    get_recurring_obligations,
    get_user_profile_memory,
)
from core.models import (
    Account,
    AdvisorConversation,
    AdvisorMemory,
    AdvisorMemorySuggestion,
    Category,
    CategoryBudget,
    CategoryGroup,
    ExpenseMonth,
    Goal,
    GoalContribution,
    Transaction,
)
from core.models import User as UserModel

User = get_user_model()


def _payload_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    return cast(dict[str, object], payload[key])


def _payload_list(payload: dict[str, object], key: str) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], payload[key])


@override_settings(USE_TZ=True)
class AdvisorToolsTests(TestCase):
    today: ClassVar[datetime.date] = datetime.date(2026, 6, 15)

    def setUp(self) -> None:
        self.user = User.objects.create_user(email="tools@example.com")
        self.other_user = User.objects.create_user(email="other-tools@example.com")
        self.account = Account.objects.create(user=self.user, name="Chequing")
        self.other_account = Account.objects.create(user=self.other_user, name="Other Chequing")

    def test_empty_data_returns_compact_payloads_with_missing_balance_metadata(self) -> None:
        spending = get_recent_spending_brief(
            self.user,
            start_date=datetime.date(2026, 6, 1),
            end_date=datetime.date(2026, 6, 30),
        )
        budget = get_budget_position(self.user, month=datetime.date(2026, 6, 1))
        cash_flow = get_cash_flow_summary(self.user, months=2, end_month=datetime.date(2026, 6, 1))
        recurring = get_recurring_obligations(self.user)
        goals = get_goal_status(self.user, today=self.today)

        self.assertEqual(spending["total_spent"], 0.0)
        self.assertEqual(_payload_dict(budget, "totals"), {"budget": 0.0, "spent": 0.0, "remaining": 0.0})
        self.assertEqual(cash_flow["average_net_cash_flow"], 0.0)
        self.assertEqual(recurring["items"], [])
        self.assertEqual(goals["goals"], [])
        self.assertTrue(_payload_dict(spending, "missing_data")["accounts_lack_current_balances"])

    def test_user_profile_memory_returns_only_approved_user_memory(self) -> None:
        AdvisorMemory.objects.create(
            user=self.user,
            key="cash_buffer_preference",
            value="Wants three months of expenses before large purchases.",
            source=AdvisorMemory.SOURCE_MANUAL,
        )
        AdvisorMemory.objects.create(
            user=self.other_user,
            key="cash_buffer_preference",
            value="Other user's preference.",
            source=AdvisorMemory.SOURCE_MANUAL,
        )

        payload = get_user_profile_memory(self.user)

        self.assertEqual(payload["count"], 1)
        items = _payload_list(payload, "items")
        self.assertEqual(items[0]["key"], "cash_buffer_preference")
        self.assertEqual(items[0]["value"], "Wants three months of expenses before large purchases.")

    def test_create_memory_suggestion_creates_inactive_pending_suggestion_only(self) -> None:
        conversation = AdvisorConversation.objects.create(user=self.user, title="Memory chat")

        payload = create_memory_suggestion(
            self.user,
            conversation=conversation,
            key="cash_buffer_preference",
            suggested_value="Wants three months of expenses before large purchases.",
            rationale="The user stated this preference.",
        )

        suggestion = AdvisorMemorySuggestion.objects.get()
        self.assertEqual(payload["status"], AdvisorMemorySuggestion.STATUS_PENDING)
        self.assertFalse(payload["active"])
        self.assertEqual(suggestion.user, self.user)
        self.assertEqual(suggestion.conversation, conversation)
        self.assertEqual(suggestion.status, AdvisorMemorySuggestion.STATUS_PENDING)
        self.assertFalse(AdvisorMemory.objects.filter(user=self.user, key="cash_buffer_preference").exists())

    def test_create_memory_suggestion_rejects_transaction_derived_context(self) -> None:
        conversation = AdvisorConversation.objects.create(user=self.user, title="Memory chat")

        with self.assertRaises(ValidationError):
            create_memory_suggestion(
                self.user,
                conversation=conversation,
                key="salary",
                suggested_value="Monthly salary is $5000 inferred from transactions.",
                rationale="Calculated from payroll transactions.",
            )

        self.assertFalse(AdvisorMemorySuggestion.objects.filter(user=self.user, key="salary").exists())

    def test_recent_spending_brief_supports_date_ranges_caps_evidence_and_isolates_users(self) -> None:
        grocery = self._category("Grocery", expense_type="variable")
        dining = self._category("Dining", expense_type="variable")
        other_grocery = self._category("Grocery", user=self.other_user, expense_type="variable")
        june = self._month(datetime.date(2026, 6, 1))
        other_june = self._month(datetime.date(2026, 6, 1), user=self.other_user)
        self._transaction(june, "Supermarket", "125.40", datetime.date(2026, 6, 2), grocery)
        self._transaction(june, "Cafe", "25.10", datetime.date(2026, 6, 3), dining)
        self._transaction(june, "Old Grocery", "99.00", datetime.date(2026, 5, 30), grocery)
        self._transaction(
            other_june,
            "Other Market",
            "999.00",
            datetime.date(2026, 6, 2),
            other_grocery,
            self.other_account,
        )

        payload = get_recent_spending_brief(
            self.user,
            start_date=datetime.date(2026, 6, 1),
            end_date=datetime.date(2026, 6, 30),
            include_evidence=True,
            evidence_limit=50,
        )

        self.assertEqual(payload["total_spent"], 150.5)
        self.assertEqual(payload["transaction_count"], 2)
        top_categories = _payload_list(payload, "top_categories")
        evidence = _payload_list(payload, "evidence")
        self.assertEqual(top_categories[0], {"category": "Grocery", "amount": 125.4})
        self.assertEqual(len(evidence), 2)
        self.assertEqual(evidence[0]["merchant"], "Supermarket")

    def test_budget_position_includes_month_totals_categories_and_group_rollups(self) -> None:
        needs = CategoryGroup.objects.create(user=self.user, name="Needs")
        grocery = self._category("Grocery", expense_type="variable", category_group=needs)
        utilities = self._category("Utilities", expense_type="fixed", category_group=needs)
        june = self._month(datetime.date(2026, 6, 1))
        CategoryBudget.objects.create(user=self.user, category=grocery, amount=Decimal("100.00"))
        CategoryBudget.objects.create(user=self.user, category=utilities, amount=Decimal("200.00"))
        self._transaction(june, "Supermarket", "120.00", datetime.date(2026, 6, 2), grocery)
        self._transaction(june, "Power Bill", "165.00", datetime.date(2026, 6, 5), utilities)

        payload = get_budget_position(self.user, month=datetime.date(2026, 6, 20))

        over_budget = _payload_list(payload, "over_budget_categories")
        near_limit = _payload_list(payload, "near_limit_categories")
        rollups = _payload_list(payload, "category_group_rollups")
        self.assertEqual(_payload_dict(payload, "totals"), {"budget": 300.0, "spent": 285.0, "remaining": 15.0})
        self.assertEqual(over_budget[0]["category"], "Grocery")
        self.assertEqual(near_limit[0]["category"], "Utilities")
        self.assertEqual(rollups[0]["group_name"], "Needs")
        self.assertEqual(rollups[0]["spent"], 285.0)

    def test_cash_flow_summary_returns_multi_month_categories_average_and_trend(self) -> None:
        income = self._category("Pay", category_type="income")
        rent = self._category("Rent", expense_type="fixed")
        groceries = self._category("Groceries", expense_type="variable")
        savings = self._category("Savings", expense_type="savings_transfer")
        for month_start, income_amount in [
            (datetime.date(2026, 4, 1), "3000.00"),
            (datetime.date(2026, 5, 1), "3300.00"),
            (datetime.date(2026, 6, 1), "3600.00"),
        ]:
            month = self._month(month_start)
            self._transaction(month, "Payroll", income_amount, month_start, income, transaction_type="income")
            self._transaction(month, "Rent", "1200.00", month_start, rent)
            self._transaction(month, "Groceries", "500.00", month_start, groceries)
            self._transaction(month, "TFSA Transfer", "300.00", month_start, savings)

        payload = get_cash_flow_summary(self.user, months=3, end_month=datetime.date(2026, 6, 1))

        months = _payload_list(payload, "months")
        self.assertEqual(months[0]["net_cash_flow"], 1000.0)
        self.assertEqual(months[2]["income"], 3600.0)
        self.assertEqual(payload["average_net_cash_flow"], 1300.0)
        self.assertEqual(payload["trend"], "improving")

    def test_recurring_obligations_use_existing_detection_with_estimates_and_confidence(self) -> None:
        subscriptions = self._category("Subscriptions", expense_type="fixed")
        for month_start in [datetime.date(2026, 1, 1), datetime.date(2026, 2, 1), datetime.date(2026, 3, 1)]:
            month = self._month(month_start)
            self._transaction(month, "Netflix Subscription", "15.99", month_start, subscriptions)

        payload = get_recurring_obligations(self.user)

        items = _payload_list(payload, "items")
        summary = _payload_dict(payload, "summary")
        self.assertEqual(items[0]["description"], "Netflix Subscription")
        self.assertEqual(items[0]["monthly_estimate"], 15.99)
        self.assertEqual(items[0]["annual_estimate"], 191.88)
        self.assertEqual(items[0]["confidence"], "medium")
        self.assertEqual(summary["estimated_monthly_total"], 15.99)

    def test_goal_status_covers_all_goal_types_selected_goal_and_user_isolation(self) -> None:
        savings_goal = Goal.objects.create(
            user=self.user,
            name="Emergency Fund",
            goal_type="savings",
            target_amount=Decimal("1200.00"),
            deadline=datetime.date(2026, 12, 15),
        )
        GoalContribution.objects.create(goal=savings_goal, amount=Decimal("300.00"), date=datetime.date(2026, 3, 15))
        debt_category = self._category("Debt Payment", expense_type="fixed")
        debt_goal = Goal.objects.create(
            user=self.user,
            name="Card Paydown",
            goal_type="debt",
            target_amount=Decimal("600.00"),
            category=debt_category,
        )
        spending_category = self._category("Dining", expense_type="variable")
        spending_goal = Goal.objects.create(
            user=self.user,
            name="Dining Cap",
            goal_type="spending",
            target_amount=Decimal("400.00"),
            category=spending_category,
        )
        other_goal = Goal.objects.create(
            user=self.other_user,
            name="Other Goal",
            goal_type="savings",
            target_amount=Decimal("1.00"),
        )
        june = self._month(datetime.date(2026, 6, 1))
        self._transaction(june, "Card Payment", "200.00", datetime.date(2026, 6, 1), debt_category)
        self._transaction(june, "Restaurant", "100.00", datetime.date(2026, 6, 10), spending_category)

        payload = get_goal_status(self.user, goal_id=savings_goal.id, today=self.today)

        goals = _payload_list(payload, "goals")
        selected_goal = _payload_dict(payload, "selected_goal")
        names = {goal["name"] for goal in goals}
        self.assertEqual(names, {"Emergency Fund", "Card Paydown", "Dining Cap"})
        self.assertNotIn(other_goal.name, names)
        self.assertEqual(selected_goal["name"], savings_goal.name)
        self.assertEqual(selected_goal["progress"], 300.0)
        self.assertEqual(selected_goal["gap"], 900.0)
        self.assertEqual(selected_goal["required_monthly_amount"], 147.54)
        self.assertEqual(debt_goal.user, self.user)
        self.assertEqual(spending_goal.user, self.user)

    def _category(
        self,
        name: str,
        *,
        user: UserModel | None = None,
        category_type: str = "expense",
        expense_type: str = "variable",
        category_group: CategoryGroup | None = None,
    ) -> Category:
        owner = user or self.user
        category, _created = Category.objects.update_or_create(
            user=owner,
            name=name,
            defaults={
                "category_type": category_type,
                "expense_type": expense_type,
                "category_group": category_group,
            },
        )
        return category

    def _month(self, month_start: datetime.date, *, user: UserModel | None = None) -> ExpenseMonth:
        owner = user or self.user
        month, _created = ExpenseMonth.objects.get_or_create(
            user=owner,
            month=month_start,
            defaults={"label": month_start.strftime("%B %Y")},
        )
        return month

    def _transaction(
        self,
        month: ExpenseMonth,
        description: str,
        amount: str,
        date: datetime.date,
        category: Category,
        account: Account | None = None,
        *,
        transaction_type: str = "expense",
    ) -> Transaction:
        return Transaction.objects.create(
            expense_month=month,
            date=date,
            description=description,
            amount=Decimal(amount),
            account=account or self.account,
            transaction_type=transaction_type,
            category=category,
        )
