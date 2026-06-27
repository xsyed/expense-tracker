from __future__ import annotations

import datetime
import json
from decimal import Decimal
from typing import cast

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.forms import CategoryForm
from core.models import Category, CategoryBudget, CategoryGroup, ExpenseMonth, Transaction

User = get_user_model()


def _group_by_name(rows: list[dict[str, object]], name: str) -> dict[str, object]:
    for row in rows:
        if row["group_name"] == name:
            return row
    raise AssertionError(f"Group {name} not found in {rows}")


class CategoryGroupModelFormTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="category-groups@example.com")
        Category.objects.filter(user=self.user).delete()

    def test_group_names_are_unique_per_user(self) -> None:
        CategoryGroup.objects.create(user=self.user, name="Food")

        with self.assertRaises(IntegrityError), transaction.atomic():
            CategoryGroup.objects.create(user=self.user, name="Food")

    def test_different_users_can_reuse_group_names(self) -> None:
        other_user = User.objects.create_user(email="other-category-groups@example.com")

        CategoryGroup.objects.create(user=self.user, name="Food")
        group = CategoryGroup.objects.create(user=other_user, name="Food")

        self.assertEqual(group.name, "Food")

    def test_expense_category_can_be_assigned_to_group(self) -> None:
        group = CategoryGroup.objects.create(user=self.user, name="Food")

        form = CategoryForm(
            data={"name": "Tiffin", "category_type": "expense", "category_group": str(group.id)},
            user=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors)
        category = form.save(commit=False)
        category.user = self.user
        category.save()
        self.assertEqual(category.category_group, group)

    def test_income_category_clears_group_assignment(self) -> None:
        group = CategoryGroup.objects.create(user=self.user, name="Food")

        form = CategoryForm(
            data={"name": "Salary", "category_type": "income", "category_group": str(group.id)},
            user=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors)
        category = form.save(commit=False)
        category.user = self.user
        category.save()
        self.assertIsNone(category.category_group)

    def test_deleting_group_keeps_category_and_ungroups_it(self) -> None:
        group = CategoryGroup.objects.create(user=self.user, name="Food")
        category = Category.objects.create(
            user=self.user,
            name="Grocery",
            category_type="expense",
            category_group=group,
        )

        group.delete()

        category.refresh_from_db()
        self.assertIsNone(category.category_group)
        self.assertTrue(Category.objects.filter(pk=category.pk).exists())


class CategoryGroupReportingTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="category-group-reporting@example.com")
        Category.objects.filter(user=self.user).delete()
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self.client.force_login(self.user)
        self.month = ExpenseMonth.objects.create(
            user=self.user,
            label="May 2026",
            month=datetime.date(2026, 5, 1),
        )
        self.food = CategoryGroup.objects.create(user=self.user, name="Food")
        self.tiffin = Category.objects.create(
            user=self.user,
            name="Tiffin",
            category_type="expense",
            category_group=self.food,
        )
        self.grocery = Category.objects.create(
            user=self.user,
            name="Grocery",
            category_type="expense",
            category_group=self.food,
        )
        self.rent = Category.objects.create(user=self.user, name="Rent", category_type="expense")
        self.salary = Category.objects.create(user=self.user, name="Salary", category_type="income")
        CategoryBudget.objects.create(user=self.user, category=self.grocery, amount=Decimal("100.00"))
        Transaction.objects.create(
            expense_month=self.month,
            date=datetime.date(2026, 5, 2),
            description="Tiffin",
            amount=Decimal("40.00"),
            transaction_type="expense",
            category=self.tiffin,
        )
        Transaction.objects.create(
            expense_month=self.month,
            date=datetime.date(2026, 5, 3),
            description="Grocery",
            amount=Decimal("60.00"),
            transaction_type="expense",
            category=self.grocery,
        )
        Transaction.objects.create(
            expense_month=self.month,
            date=datetime.date(2026, 5, 4),
            description="Rent",
            amount=Decimal("900.00"),
            transaction_type="expense",
            category=self.rent,
        )
        Transaction.objects.create(
            expense_month=self.month,
            date=datetime.date(2026, 5, 5),
            description="Cash",
            amount=Decimal("25.00"),
            transaction_type="expense",
            category=None,
        )
        Transaction.objects.create(
            expense_month=self.month,
            date=datetime.date(2026, 5, 6),
            description="Salary",
            amount=Decimal("3000.00"),
            transaction_type="income",
            category=self.salary,
        )

    def test_budget_insights_returns_group_spend_and_category_budget_data(self) -> None:
        response = self.client.get(reverse("budget_data"), {"month": "2026-05"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        categories = cast(list[dict[str, object]], data["categories"])
        self.assertEqual(categories[0]["name"], "Grocery")
        self.assertEqual(categories[0]["budgeted"], 100.0)
        self.assertEqual(categories[0]["spent"], 60.0)

        groups = cast(list[dict[str, object]], data["groups"])
        self.assertEqual([group["group_name"] for group in groups], ["Ungrouped", "Food"])
        food = _group_by_name(groups, "Food")
        self.assertEqual(food["spent"], 100.0)
        food_categories = cast(list[dict[str, object]], food["categories"])
        self.assertEqual([row["category_name"] for row in food_categories], ["Grocery", "Tiffin"])

    def test_category_spend_returns_expense_groups_and_income_separately(self) -> None:
        response = self.client.get(reverse("category_spend_data"), {"month": "2026-05"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        groups = cast(list[dict[str, object]], data["expense_groups"])
        food = _group_by_name(groups, "Food")
        ungrouped = _group_by_name(groups, "Ungrouped")
        self.assertEqual(food["spent"], 100.0)
        self.assertEqual(ungrouped["spent"], 925.0)
        income = cast(list[dict[str, object]], data["income"])
        self.assertEqual(income[0]["category"], "Salary")

    def test_month_detail_renders_group_spend(self) -> None:
        response = self.client.get(reverse("month_detail", kwargs={"pk": self.month.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Category Groups")
        self.assertContains(response, "Food")
        self.assertContains(response, "Grocery")
        self.assertContains(response, "$100.00")

    def test_transaction_mutations_include_category_group_rows(self) -> None:
        create_data = self._post_json_success(
            "transaction_create",
            {
                "date": "2026-05-07",
                "description": "Lunch",
                "amount": "30.00",
                "transaction_type": "expense",
                "category_id": str(self.tiffin.id),
            },
            month_id=self.month.id,
        )
        self.assert_group_spend(create_data, "Food", 130.0)

        transaction_data = cast(dict[str, object], create_data["transaction"])
        tx_id = int(cast(int, transaction_data["id"]))
        update_data = self._post_json_success(
            "transaction_update",
            {"field": "amount", "value": "50.00"},
            month_id=self.month.id,
            tx_id=tx_id,
        )
        self.assert_group_spend(update_data, "Food", 150.0)

        delete_data = self._post_json_success(
            "transaction_delete",
            {},
            month_id=self.month.id,
            tx_id=tx_id,
        )
        self.assert_group_spend(delete_data, "Food", 100.0)

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

    def assert_group_spend(self, data: dict[str, object], group_name: str, expected: float) -> None:
        rows = cast(list[dict[str, object]], data["category_group_rows"])
        self.assertEqual(_group_by_name(rows, group_name)["spent"], expected)
