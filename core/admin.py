from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Category, ExpenseMonth, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "is_staff", "is_active", "date_joined")
    list_filter = ("is_staff", "is_active")
    search_fields = ("email",)
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )
    filter_horizontal = ("groups", "user_permissions")


@admin.register(ExpenseMonth)
class ExpenseMonthAdmin(admin.ModelAdmin):
    list_display = ("label", "month", "user", "created_at")
    list_filter = ("month",)
    search_fields = ("label", "user__email")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "created_at")
    list_filter = ("user",)
    search_fields = ("name", "user__email")
    ordering = ("user", "name")
