from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    AdvisorConversation,
    AdvisorMemory,
    AdvisorMemorySuggestion,
    AdvisorMessage,
    AdvisorRun,
    Category,
    CategoryBudget,
    CategoryGroup,
    ExpenseMonth,
    Goal,
    GoalContribution,
    MerchantRule,
    Transaction,
    User,
    UserGridPreference,
)


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
    list_display = ("name", "user", "category_type", "category_group", "created_at")
    list_filter = ("user", "category_type", "category_group")
    search_fields = ("name", "user__email")
    ordering = ("user", "name")


@admin.register(CategoryGroup)
class CategoryGroupAdmin(admin.ModelAdmin[CategoryGroup]):
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


@admin.register(CategoryBudget)
class CategoryBudgetAdmin(admin.ModelAdmin[CategoryBudget]):
    list_display = ("user", "category", "amount")
    list_filter = ("user",)
    search_fields = ("user__email", "category__name")


@admin.register(MerchantRule)
class MerchantRuleAdmin(admin.ModelAdmin[MerchantRule]):
    list_display = ("user", "normalized_name", "category", "last_used")
    list_filter = ("user",)
    search_fields = ("normalized_name", "user__email", "category__name")


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin[Goal]):
    list_display = ("name", "user", "goal_type", "target_amount", "deadline", "created_at")
    list_filter = ("goal_type",)
    search_fields = ("name", "user__email")


@admin.register(GoalContribution)
class GoalContributionAdmin(admin.ModelAdmin[GoalContribution]):
    list_display = ("goal", "amount", "date", "note", "created_at")
    list_filter = ("date",)
    ordering = ("-date",)


@admin.register(UserGridPreference)
class UserGridPreferenceAdmin(admin.ModelAdmin[UserGridPreference]):
    list_display = ("user", "column_visibility")
    search_fields = ("user__email",)


@admin.register(AdvisorConversation)
class AdvisorConversationAdmin(admin.ModelAdmin[AdvisorConversation]):
    list_display = ("title", "user", "is_archived", "created_at", "updated_at")
    list_filter = ("is_archived", "created_at")
    search_fields = ("title", "summary", "user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AdvisorMessage)
class AdvisorMessageAdmin(admin.ModelAdmin[AdvisorMessage]):
    list_display = ("conversation", "role", "created_at", "linked_run")
    list_filter = ("role", "created_at")
    search_fields = ("content", "conversation__title", "conversation__user__email")
    readonly_fields = ("created_at",)


@admin.register(AdvisorRun)
class AdvisorRunAdmin(admin.ModelAdmin[AdvisorRun]):
    list_display = ("conversation", "user_message", "status", "model", "created_at", "updated_at")
    list_filter = ("status", "model", "created_at")
    search_fields = ("conversation__title", "conversation__user__email", "final_response", "error_message")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AdvisorMemory)
class AdvisorMemoryAdmin(admin.ModelAdmin[AdvisorMemory]):
    list_display = ("user", "key", "source", "created_at", "updated_at")
    list_filter = ("source", "created_at")
    search_fields = ("user__email", "key", "value")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AdvisorMemorySuggestion)
class AdvisorMemorySuggestionAdmin(admin.ModelAdmin[AdvisorMemorySuggestion]):
    list_display = ("user", "conversation", "key", "status", "created_at", "resolved_at")
    list_filter = ("status", "created_at", "resolved_at")
    search_fields = ("user__email", "conversation__title", "key", "suggested_value", "rationale")
    readonly_fields = ("created_at", "resolved_at")
