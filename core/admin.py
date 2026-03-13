from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Category, CategoryBudget, CSVUpload, ExpenseMonth, Transaction, User, UserGridPreference


@admin.register(User)
class UserAdmin(BaseUserAdmin[Any]):
    list_display = ("email", "is_staff", "is_active", "date_joined")
    list_filter = ("is_staff", "is_active")
    search_fields = ("email",)
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)
    filter_horizontal = ("groups", "user_permissions")


@admin.register(ExpenseMonth)
class ExpenseMonthAdmin(admin.ModelAdmin[ExpenseMonth]):
    list_display = ("label", "month", "user", "created_at")
    list_filter = ("month",)
    search_fields = ("label", "user__email")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin[Category]):
    list_display = ("name", "user", "created_at")
    list_filter = ("user",)
    search_fields = ("name", "user__email")
    ordering = ("user", "name")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin[Transaction]):
    list_display = ("expense_month", "date", "description", "amount", "transaction_type", "category")
    list_filter = ("transaction_type", "expense_month")
    search_fields = ("description",)
    ordering = ("-date",)


@admin.register(CSVUpload)
class CSVUploadAdmin(admin.ModelAdmin[CSVUpload]):
    list_display = ("expense_month", "filename", "row_count", "uploaded_at")
    list_filter = ("expense_month",)
    ordering = ("-uploaded_at",)


@admin.register(CategoryBudget)
class CategoryBudgetAdmin(admin.ModelAdmin[CategoryBudget]):
    list_display = ("user", "category", "amount")
    list_filter = ("user",)
    search_fields = ("user__email", "category__name")


@admin.register(UserGridPreference)
class UserGridPreferenceAdmin(admin.ModelAdmin[UserGridPreference]):
    list_display = ("user", "column_visibility")
    search_fields = ("user__email",)
