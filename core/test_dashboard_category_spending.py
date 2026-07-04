from __future__ import annotations

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import Category, ExpenseMonth, Transaction

User = get_user_model()


class DashboardCategorySpendingTableTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="dashboard-table@example.com")
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self.client.force_login(self.user)
        self.grocery = Category.objects.create(user=self.user, name="Groceries")
        self.dining = Category.objects.create(user=self.user, name="Dining")
        self.current_month = ExpenseMonth.objects.create(
            user=self.user,
            label="Current",
            month=self._month_start(0),
        )
        self.previous_month = ExpenseMonth.objects.create(
            user=self.user,
            label="Previous",
            month=self._month_start(1),
        )
        self.old_month = ExpenseMonth.objects.create(
            user=self.user,
            label="Old",
            month=self._month_start(13),
        )

    def _month_start(self, months_ago: int) -> datetime.date:
        today = datetime.date.today()
        year = today.year
        month = today.month - months_ago
        while month <= 0:
            month += 12
            year -= 1
        return datetime.date(year, month, 1)

    def _create_expense(
        self,
        expense_month: ExpenseMonth,
        amount: str,
        category: Category | None,
        day: int = 1,
    ) -> None:
        Transaction.objects.create(
            expense_month=expense_month,
            date=expense_month.month.replace(day=day),
            description="Expense",
            amount=amount,
            transaction_type="expense",
            category=category,
        )

    def test_category_spending_table_requires_login(self) -> None:
        self.client.logout()

        response = self.client.get("/api/charts/category-spending-table/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/account/login/", response["Location"])

    def test_category_spending_table_returns_sorted_rows_with_metrics(self) -> None:
        self._create_expense(self.current_month, "100.00", self.grocery)
        self._create_expense(self.current_month, "40.00", self.dining)
        self._create_expense(self.previous_month, "50.00", self.grocery)
        self._create_expense(self.previous_month, "10.00", None)

        response = self.client.get("/api/charts/category-spending-table/?months=3")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total_expenses"], 200.0)
        self.assertEqual(
            payload["rows"],
            [
                {"category": "Groceries", "total": 150.0, "share": 75.0, "avg_monthly": 75.0},
                {"category": "Dining", "total": 40.0, "share": 20.0, "avg_monthly": 20.0},
                {"category": "Unclassified", "total": 10.0, "share": 5.0, "avg_monthly": 5.0},
            ],
        )

    def test_category_spending_table_honors_all_and_numeric_ranges(self) -> None:
        self._create_expense(self.current_month, "100.00", self.grocery)
        self._create_expense(self.old_month, "500.00", self.dining)

        recent_response = self.client.get("/api/charts/category-spending-table/?months=3")
        all_response = self.client.get("/api/charts/category-spending-table/?months=all")

        self.assertEqual(recent_response.status_code, 200)
        self.assertEqual(all_response.status_code, 200)
        self.assertEqual(
            recent_response.json()["rows"],
            [{"category": "Groceries", "total": 100.0, "share": 100.0, "avg_monthly": 100.0}],
        )
        self.assertEqual(
            all_response.json()["rows"],
            [
                {"category": "Dining", "total": 500.0, "share": 83.3, "avg_monthly": 250.0},
                {"category": "Groceries", "total": 100.0, "share": 16.7, "avg_monthly": 50.0},
            ],
        )
