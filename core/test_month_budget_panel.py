from __future__ import annotations

import datetime
import json
from decimal import Decimal
from typing import cast

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import Category, CategoryBudget, ExpenseMonth, Transaction
from core.month_budget_rows import build_month_budget_rows

User = get_user_model()


class MonthBudgetRowsTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="budget-panel@example.com")
        Category.objects.filter(user=self.user).delete()
        self.month = ExpenseMonth.objects.create(
            user=self.user,
            label="May 2026",
            month=datetime.date(2026, 5, 1),
        )
        self.rent = Category.objects.create(user=self.user, name="Rent", category_type="expense")
        self.grocery = Category.objects.create(user=self.user, name="Grocery", category_type="expense")
        self.dining = Category.objects.create(user=self.user, name="Dining", category_type="expense")
        self.zero_spend = Category.objects.create(user=self.user, name="Zero Spend", category_type="expense")
        self.salary = Category.objects.create(user=self.user, name="Salary", category_type="income")
        CategoryBudget.objects.create(user=self.user, category=self.rent, amount=Decimal("1000.00"))
        CategoryBudget.objects.create(user=self.user, category=self.grocery, amount=Decimal("100.00"))
        CategoryBudget.objects.create(user=self.user, category=self.zero_spend, amount=Decimal("50.00"))
        Transaction.objects.create(
            expense_month=self.month,
            date=datetime.date(2026, 5, 2),
            description="Rent",
            amount=Decimal("1250.00"),
            transaction_type="expense",
            category=self.rent,
        )
        Transaction.objects.create(
            expense_month=self.month,
            date=datetime.date(2026, 5, 3),
            description="Grocery",
            amount=Decimal("80.00"),
            transaction_type="expense",
            category=self.grocery,
        )
        Transaction.objects.create(
            expense_month=self.month,
            date=datetime.date(2026, 5, 4),
            description="Restaurant",
            amount=Decimal("150.00"),
            transaction_type="expense",
            category=self.dining,
        )
        Transaction.objects.create(
            expense_month=self.month,
            date=datetime.date(2026, 5, 5),
            description="Paycheque",
            amount=Decimal("9000.00"),
            transaction_type="income",
            category=self.salary,
        )
        Transaction.objects.create(
            expense_month=self.month,
            date=datetime.date(2026, 5, 6),
            description="Wrong type category",
            amount=Decimal("999.00"),
            transaction_type="expense",
            category=self.salary,
        )

    def test_budget_rows_include_spent_expense_categories_sorted_by_spend(self) -> None:
        rows = build_month_budget_rows(self.month)

        self.assertEqual([row["category_name"] for row in rows], ["Rent", "Dining", "Grocery"])
        self.assertEqual(rows[0]["status"], "over")
        self.assertEqual(rows[0]["remaining"], -250.0)
        self.assertEqual(rows[1]["status"], "unbudgeted")
        self.assertIsNone(rows[1]["budget"])
        self.assertEqual(rows[2]["status"], "near")
        self.assertEqual(rows[2]["progress_percent"], 80.0)


class MonthBudgetPanelViewTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="budget-view@example.com")
        Category.objects.filter(user=self.user).delete()
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self.client.force_login(self.user)
        self.month = ExpenseMonth.objects.create(
            user=self.user,
            label="June 2026",
            month=datetime.date(2026, 6, 1),
        )
        self.category = Category.objects.create(user=self.user, name="Fuel", category_type="expense")
        self.unbudgeted_category = Category.objects.create(user=self.user, name="Parking", category_type="expense")
        CategoryBudget.objects.create(user=self.user, category=self.category, amount=Decimal("200.00"))
        Transaction.objects.create(
            expense_month=self.month,
            date=datetime.date(2026, 6, 2),
            description="Gas",
            amount=Decimal("25.00"),
            transaction_type="expense",
            category=self.category,
        )
        Transaction.objects.create(
            expense_month=self.month,
            date=datetime.date(2026, 6, 3),
            description="Parking",
            amount=Decimal("12.00"),
            transaction_type="expense",
            category=self.unbudgeted_category,
        )

    def test_month_detail_renders_category_budget_panel(self) -> None:
        response = self.client.get(reverse("month_detail", kwargs={"pk": self.month.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Category Budgets")
        self.assertContains(response, "Fuel")
        self.assertContains(response, "$25.00")
        self.assertContains(response, "$200.00 budget")
        self.assertContains(response, "On track")
        self.assertContains(response, "Parking")
        self.assertContains(response, "$12.00")
        self.assertNotContains(response, "Unbudgeted")
        self.assertNotContains(response, "Parking budget usage")


class TransactionBudgetResponseTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="budget-response@example.com")
        Category.objects.filter(user=self.user).delete()
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self.client.force_login(self.user)
        self.month = ExpenseMonth.objects.create(
            user=self.user,
            label="July 2026",
            month=datetime.date(2026, 7, 1),
        )
        self.category = Category.objects.create(user=self.user, name="Groceries", category_type="expense")
        CategoryBudget.objects.create(user=self.user, category=self.category, amount=Decimal("100.00"))

    def _post_json_success(
        self,
        url_name: str,
        payload: dict[str, object],
        **kwargs: int,
    ) -> dict[str, object]:
        response = self.client.post(
            reverse(url_name, kwargs=kwargs),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return cast(dict[str, object], response.json())

    def test_transaction_mutation_responses_include_budget_rows(self) -> None:
        create_data = self._post_json_success(
            "transaction_create",
            {
                "date": "2026-07-03",
                "description": "Groceries",
                "amount": "40.00",
                "transaction_type": "expense",
                "category_id": str(self.category.id),
            },
            month_id=self.month.id,
        )
        create_budget_rows = cast(list[dict[str, object]], create_data["budget_rows"])
        self.assertEqual(create_budget_rows[0]["spent"], 40.0)

        transaction = cast(dict[str, object], create_data["transaction"])
        tx_id = int(cast(int, transaction["id"]))
        update_data = self._post_json_success(
            "transaction_update",
            {"field": "amount", "value": "90.00"},
            month_id=self.month.id,
            tx_id=tx_id,
        )
        update_budget_rows = cast(list[dict[str, object]], update_data["budget_rows"])
        self.assertEqual(update_budget_rows[0]["status"], "near")
        self.assertEqual(update_budget_rows[0]["spent"], 90.0)

        bulk_delete_data = self._post_json_success(
            "transaction_bulk_delete",
            {"ids": [tx_id]},
            month_id=self.month.id,
        )
        bulk_delete_budget_rows = cast(list[dict[str, object]], bulk_delete_data["budget_rows"])
        self.assertEqual(bulk_delete_budget_rows, [])
