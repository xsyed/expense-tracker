from __future__ import annotations

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.forms import GoalForm
from core.goal_progress import debt_goal_progress, savings_goal_progress
from core.models import Category, ExpenseMonth, Goal, GoalContribution, Transaction

User = get_user_model()


class DebtGoalTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="debt@example.com")
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self.client.force_login(self.user)
        self.expense_category = Category.objects.create(
            user=self.user,
            name="Loan Payment",
            category_type="expense",
            expense_type="fixed",
        )
        self.other_expense_category = Category.objects.create(
            user=self.user,
            name="Dining",
            category_type="expense",
            expense_type="variable",
        )
        self.income_category = Category.objects.create(
            user=self.user,
            name="Paycheque",
            category_type="income",
        )
        self.january = ExpenseMonth.objects.create(
            user=self.user,
            label="Jan 2026",
            month=datetime.date(2026, 1, 1),
        )
        self.february = ExpenseMonth.objects.create(
            user=self.user,
            label="Feb 2026",
            month=datetime.date(2026, 2, 1),
        )

    def test_debt_goal_type_is_valid(self) -> None:
        self.assertIn(("debt", "Debt"), Goal.GOAL_TYPES)

    def test_debt_goal_without_category_is_rejected(self) -> None:
        form = GoalForm(
            data={"name": "Car Loan", "goal_type": "debt", "target_amount": "1000.00"},
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_debt_goal_with_income_category_is_rejected(self) -> None:
        form = GoalForm(
            data={
                "name": "Car Loan",
                "goal_type": "debt",
                "target_amount": "1000.00",
                "category": str(self.income_category.pk),
            },
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("expense category", form.errors["category"][0])

    def test_debt_goal_with_expense_category_is_accepted(self) -> None:
        form = GoalForm(
            data={
                "name": "Car Loan",
                "goal_type": "debt",
                "target_amount": "1000.00",
                "category": str(self.expense_category.pk),
            },
            user=self.user,
        )

        self.assertTrue(form.is_valid())

    def test_spending_goal_with_income_category_is_rejected(self) -> None:
        form = GoalForm(
            data={
                "name": "Dining Limit",
                "goal_type": "spending",
                "target_amount": "300.00",
                "category": str(self.income_category.pk),
            },
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("expense category", form.errors["category"][0])

    def test_savings_goal_with_income_category_is_rejected(self) -> None:
        form = GoalForm(
            data={
                "name": "Rainy Fund",
                "goal_type": "savings",
                "target_amount": "1000.00",
                "category": str(self.income_category.pk),
            },
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("expense category", form.errors["category"][0])

    def test_savings_progress_tracks_matching_expenses_and_manual_contributions(self) -> None:
        goal = Goal.objects.create(
            user=self.user,
            name="Rainy Fund",
            goal_type="savings",
            target_amount=Decimal("1000.00"),
            category=self.expense_category,
        )
        self._set_goal_created_at(goal, datetime.date(2026, 1, 15))
        GoalContribution.objects.create(goal=goal, amount=Decimal("25.00"), date=datetime.date(2026, 1, 20))
        self._create_transaction("Too early", "50.00", datetime.date(2026, 1, 14), self.expense_category)
        self._create_transaction("Emergency transfer", "75.00", datetime.date(2026, 1, 15), self.expense_category)
        self._create_transaction("Later transfer", "100.00", datetime.date(2026, 2, 1), self.expense_category)
        self._create_transaction("Other category", "200.00", datetime.date(2026, 2, 1), self.other_expense_category)

        self.assertEqual(savings_goal_progress(goal), Decimal("200"))

    def test_savings_progress_updates_each_goal_sharing_category_and_caps_at_target(self) -> None:
        small_goal = Goal.objects.create(
            user=self.user,
            name="Small Fund",
            goal_type="savings",
            target_amount=Decimal("150.00"),
            category=self.expense_category,
        )
        large_goal = Goal.objects.create(
            user=self.user,
            name="Large Fund",
            goal_type="savings",
            target_amount=Decimal("250.00"),
            category=self.expense_category,
        )
        self._set_goal_created_at(small_goal, datetime.date(2026, 1, 15))
        self._set_goal_created_at(large_goal, datetime.date(2026, 1, 15))
        self._create_transaction("First transfer", "100.00", datetime.date(2026, 1, 15), self.expense_category)
        self._create_transaction("Second transfer", "100.00", datetime.date(2026, 2, 1), self.expense_category)
        self._create_transaction("Third transfer", "100.00", datetime.date(2026, 2, 2), self.expense_category)

        self.assertEqual(savings_goal_progress(small_goal), Decimal("150.00"))
        self.assertEqual(savings_goal_progress(large_goal), Decimal("250.00"))

    def test_debt_progress_tracks_only_matching_expenses_on_or_after_creation_date(self) -> None:
        goal = self._create_debt_goal()
        GoalContribution.objects.create(goal=goal, amount=Decimal("999.00"), date=datetime.date(2026, 1, 20))
        self._create_transaction("Too early", "50.00", datetime.date(2026, 1, 14), self.expense_category)
        self._create_transaction("Same day", "75.00", datetime.date(2026, 1, 15), self.expense_category)
        self._create_transaction("Later", "100.00", datetime.date(2026, 2, 1), self.expense_category)
        self._create_transaction("Other category", "200.00", datetime.date(2026, 2, 1), self.other_expense_category)

        self.assertEqual(debt_goal_progress(goal), Decimal("175"))

    def test_goals_insights_include_debt_progress_and_timeline(self) -> None:
        today = datetime.date.today()
        month = ExpenseMonth.objects.create(user=self.user, label="Current", month=today.replace(day=1))
        goal = Goal.objects.create(
            user=self.user,
            name="Line of Credit",
            goal_type="debt",
            target_amount=Decimal("1000.00"),
            category=self.expense_category,
            deadline=today + datetime.timedelta(days=60),
        )
        self._set_goal_created_at(goal, today - datetime.timedelta(days=1))
        self._create_transaction("Payment", "250.00", today, self.expense_category, month)

        response = self.client.get("/api/insights/goals-data/")
        data = response.json()
        debt_goal = next(g for g in data["goals"] if g["id"] == goal.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(debt_goal["progress_amount"], 250.0)
        self.assertEqual(debt_goal["pct_complete"], 25)
        self.assertEqual(debt_goal["health"], "behind")
        self.assertEqual(debt_goal["deadline"], (today + datetime.timedelta(days=60)).isoformat())
        self.assertEqual(debt_goal["days_remaining"], 60)
        self.assertEqual(debt_goal["category_name"], "Loan Payment")
        self.assertEqual(data["timeline"]["series"][0]["name"], "Line of Credit")
        self.assertEqual(data["timeline"]["series"][0]["data"], [250.0])

    def test_goals_insights_include_auto_tracked_savings_progress_and_timeline(self) -> None:
        today = datetime.date.today()
        month = ExpenseMonth.objects.create(user=self.user, label="Current", month=today.replace(day=1))
        goal = Goal.objects.create(
            user=self.user,
            name="Rainy Fund",
            goal_type="savings",
            target_amount=Decimal("1000.00"),
            category=self.expense_category,
            deadline=today + datetime.timedelta(days=60),
        )
        self._set_goal_created_at(goal, today - datetime.timedelta(days=1))
        GoalContribution.objects.create(goal=goal, amount=Decimal("25.00"), date=today)
        self._create_transaction("Emergency transfer", "250.00", today, self.expense_category, month)

        response = self.client.get("/api/insights/goals-data/")
        data = response.json()
        savings_goal = next(g for g in data["goals"] if g["id"] == goal.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(savings_goal["progress_amount"], 275.0)
        self.assertEqual(savings_goal["pct_complete"], 27)
        self.assertEqual(savings_goal["deadline"], (today + datetime.timedelta(days=60)).isoformat())
        self.assertEqual(savings_goal["category_name"], "Loan Payment")
        self.assertEqual(data["timeline"]["series"][0]["name"], "Rainy Fund")
        self.assertEqual(data["timeline"]["series"][0]["data"], [275.0])

    def test_goals_insights_caps_completed_savings_progress_and_timeline(self) -> None:
        today = datetime.date.today()
        month = ExpenseMonth.objects.create(user=self.user, label="Current", month=today.replace(day=1))
        goal = Goal.objects.create(
            user=self.user,
            name="Reached Fund",
            goal_type="savings",
            target_amount=Decimal("200.00"),
            category=self.expense_category,
            deadline=today + datetime.timedelta(days=60),
        )
        self._set_goal_created_at(goal, today - datetime.timedelta(days=1))
        GoalContribution.objects.create(goal=goal, amount=Decimal("25.00"), date=today)
        self._create_transaction("Emergency transfer", "250.00", today, self.expense_category, month)

        response = self.client.get("/api/insights/goals-data/")
        data = response.json()
        savings_goal = next(g for g in data["goals"] if g["id"] == goal.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(savings_goal["progress_amount"], 200.0)
        self.assertEqual(savings_goal["pct_complete"], 100)
        self.assertEqual(savings_goal["health"], "completed")
        self.assertEqual(data["timeline"]["series"][0]["name"], "Reached Fund")
        self.assertEqual(data["timeline"]["series"][0]["data"], [200.0])

    def test_goals_insights_orders_goals_by_nearest_deadline_with_undated_last(self) -> None:
        today = datetime.date.today()
        Goal.objects.create(
            user=self.user,
            name="Zulu Later",
            goal_type="savings",
            target_amount=Decimal("1000.00"),
            deadline=today + datetime.timedelta(days=90),
        )
        Goal.objects.create(
            user=self.user,
            name="Alpha No Deadline",
            goal_type="savings",
            target_amount=Decimal("1000.00"),
        )
        Goal.objects.create(
            user=self.user,
            name="Middle Soon",
            goal_type="savings",
            target_amount=Decimal("1000.00"),
            deadline=today + datetime.timedelta(days=30),
        )

        response = self.client.get("/api/insights/goals-data/")
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual([goal["name"] for goal in data["goals"]], ["Middle Soon", "Zulu Later", "Alpha No Deadline"])

    def test_projection_endpoint_supports_savings_and_debt_but_not_spending(self) -> None:
        debt_goal = self._create_debt_goal()
        self._create_transaction("Payment", "125.00", datetime.date(2026, 1, 15), self.expense_category)
        savings_goal = Goal.objects.create(
            user=self.user,
            name="Emergency Fund",
            goal_type="savings",
            target_amount=Decimal("500.00"),
            category=self.other_expense_category,
        )
        GoalContribution.objects.create(goal=savings_goal, amount=Decimal("50.00"), date=datetime.date(2026, 1, 20))
        self._set_goal_created_at(savings_goal, datetime.date(2026, 1, 15))
        self._create_transaction(
            "Emergency transfer",
            "75.00",
            datetime.date(2026, 1, 21),
            self.other_expense_category,
        )
        spending_goal = Goal.objects.create(
            user=self.user,
            name="Dining Limit",
            goal_type="spending",
            target_amount=Decimal("300.00"),
            category=self.other_expense_category,
        )

        debt_response = self.client.get(f"/api/insights/goals/{debt_goal.pk}/projection/")
        savings_response = self.client.get(f"/api/insights/goals/{savings_goal.pk}/projection/")
        spending_response = self.client.get(f"/api/insights/goals/{spending_goal.pk}/projection/")

        self.assertEqual(debt_response.status_code, 200)
        self.assertEqual(debt_response.json()["historical"], [{"month": "2026-01", "cumulative": 125.0}])
        self.assertEqual(savings_response.status_code, 200)
        self.assertEqual(savings_response.json()["historical"], [{"month": "2026-01", "cumulative": 125.0}])
        self.assertEqual(spending_response.status_code, 404)

    def _create_debt_goal(self) -> Goal:
        goal = Goal.objects.create(
            user=self.user,
            name="Car Loan",
            goal_type="debt",
            target_amount=Decimal("1000.00"),
            category=self.expense_category,
        )
        self._set_goal_created_at(goal, datetime.date(2026, 1, 15))
        return goal

    def _set_goal_created_at(self, goal: Goal, created_date: datetime.date) -> None:
        created_at = timezone.make_aware(datetime.datetime.combine(created_date, datetime.time(hour=12)))
        Goal.objects.filter(pk=goal.pk).update(created_at=created_at)
        goal.refresh_from_db()

    def _create_transaction(
        self,
        description: str,
        amount: str,
        date: datetime.date,
        category: Category,
        expense_month: ExpenseMonth | None = None,
    ) -> Transaction:
        month = expense_month or (self.january if date.month == 1 else self.february)
        return Transaction.objects.create(
            expense_month=month,
            date=date,
            description=description,
            amount=Decimal(amount),
            transaction_type="expense",
            category=category,
        )
