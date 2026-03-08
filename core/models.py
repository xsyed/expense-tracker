from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserManager(BaseUserManager["User"]):
    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> "User":
        if not email:
            raise ValueError("Email address is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields: Any) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return self.email


DEFAULT_CATEGORIES = [
    "Housing & Utilities",
    "Transportation",
    "Grocery",
    "Food / Uber Eats",
    "Money Transfers",
    "Savings & Investments",
    "Amazon / Online Shopping",
    "Clothing & Grooming",
    "Movies & Entertainment",
    "Donations",
    "Miscellaneous",
    "Debt Payment",
]


class Category(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "category"
        verbose_name_plural = "categories"
        unique_together = ("user", "name")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def seed_default_categories(sender: type[User], instance: User, created: bool, **kwargs: Any) -> None:
    del sender, kwargs
    if created:
        Category.objects.bulk_create([Category(user=instance, name=name) for name in DEFAULT_CATEGORIES])


class ExpenseMonth(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="expense_months",
    )
    label = models.CharField(max_length=100)
    month = models.DateField()  # day is always stored as 1, encodes year + month
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "month")
        ordering = ["-month"]
        verbose_name = "expense month"
        verbose_name_plural = "expense months"

    def __str__(self) -> str:
        return self.label

    @property
    def total_income(self) -> Decimal:
        return self.transactions.filter(transaction_type="income").aggregate(models.Sum("amount"))[
            "amount__sum"
        ] or Decimal(0)

    @property
    def total_expenses(self) -> Decimal:
        return self.transactions.filter(transaction_type="expense").aggregate(models.Sum("amount"))[
            "amount__sum"
        ] or Decimal(0)

    @property
    def net_balance(self) -> Decimal:
        return self.total_income - self.total_expenses


class Account(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="accounts",
    )
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "name")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ("income", "Income"),
        ("expense", "Expense"),
        ("unassigned", "Unassigned"),
    ]

    expense_month = models.ForeignKey(
        ExpenseMonth,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    date = models.DateField()
    description = models.CharField(max_length=500)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES,
        default="unassigned",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    source_file = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date"]

    def __str__(self) -> str:
        return f"{self.date} — {self.description} — ${self.amount}"


class CSVUpload(models.Model):
    expense_month = models.ForeignKey(
        ExpenseMonth,
        on_delete=models.CASCADE,
        related_name="csv_uploads",
    )
    filename = models.CharField(max_length=200)
    row_count = models.PositiveIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"{self.filename} ({self.row_count} rows)"


class UserGridPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="grid_preference",
    )
    column_visibility = models.JSONField(default=dict)

    def __str__(self) -> str:
        return f"Grid preference for {self.user}"
