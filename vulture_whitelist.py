# vulture_whitelist.py
#
# This file suppresses Django-specific false positives that vulture reports as
# "unused code". These names are consumed by Django's framework internals
# (metaclasses, ORM introspection, template engine, admin autodiscover) rather
# than being called directly from application code.
#
# Do NOT import this module anywhere — it is only passed to vulture on the CLI:
#   vulture core/ expense_month/ vulture_whitelist.py --min-confidence 80

from core.apps import CoreConfig
from core.models import (
    Category,
    CategoryBudget,
    CSVUpload,
    ExpenseMonth,
    Transaction,
    User,
    UserGridPreference,
    UserManager,
    seed_default_categories,
    DEFAULT_CATEGORIES,
)
from core.admin import (
    CategoryAdmin,
    CategoryBudgetAdmin,
    CSVUploadAdmin,
    ExpenseMonthAdmin,
    TransactionAdmin,
    UserAdmin,
    UserGridPreferenceAdmin,
)
from core.forms import CategoryBudgetForm, CategoryForm, ExpenseMonthEditForm, _MultipleFileInput
from core.templatetags.math_filters import floor

# ── AppConfig ──────────────────────────────────────────────────────────────────
CoreConfig.default_auto_field
CoreConfig.name

# ── Custom user model ──────────────────────────────────────────────────────────
User.USERNAME_FIELD
User.REQUIRED_FIELDS
User.objects

# ── Model Meta attributes (read by Django ORM) ─────────────────────────────────
Category.Meta.verbose_name
Category.Meta.verbose_name_plural
Category.Meta.unique_together
Category.Meta.ordering

ExpenseMonth.Meta.unique_together
ExpenseMonth.Meta.ordering
ExpenseMonth.Meta.verbose_name
ExpenseMonth.Meta.verbose_name_plural

Transaction.Meta.ordering
Transaction.TRANSACTION_TYPES

CSVUpload.Meta.ordering

CategoryBudget.Meta.unique_together
CategoryBudget.Meta.verbose_name
CategoryBudget.Meta.verbose_name_plural

# ── Signal receiver ────────────────────────────────────────────────────────────
seed_default_categories

# ── UserManager ────────────────────────────────────────────────────────────────
UserManager.create_superuser

# ── Admin class attributes (read by ModelAdmin metaclass) ─────────────────────
UserAdmin.list_display
UserAdmin.list_filter
UserAdmin.search_fields
UserAdmin.ordering
UserAdmin.fieldsets
UserAdmin.add_fieldsets
UserAdmin.filter_horizontal

ExpenseMonthAdmin.list_display
ExpenseMonthAdmin.list_filter
ExpenseMonthAdmin.search_fields

CategoryAdmin.list_display
CategoryAdmin.list_filter
CategoryAdmin.search_fields
CategoryAdmin.ordering

TransactionAdmin.list_display
TransactionAdmin.list_filter
TransactionAdmin.search_fields
TransactionAdmin.ordering

CSVUploadAdmin.list_display
CSVUploadAdmin.list_filter
CSVUploadAdmin.ordering

UserGridPreferenceAdmin.list_display
UserGridPreferenceAdmin.search_fields

CategoryBudgetAdmin.list_display
CategoryBudgetAdmin.list_filter
CategoryBudgetAdmin.search_fields

# ── Form Meta attributes ───────────────────────────────────────────────────────
CategoryForm.Meta.model
CategoryForm.Meta.fields
CategoryForm.Meta.widgets

ExpenseMonthEditForm.Meta.model
ExpenseMonthEditForm.Meta.fields
ExpenseMonthEditForm.Meta.widgets

# ── Custom FileInput attribute (read by Django's form rendering) ───────────────
_MultipleFileInput.allow_multiple_selected

# ── Template tag ──────────────────────────────────────────────────────────────
floor

# ── Django settings (read by Django at startup) ────────────────────────────────
# These live in expense_month/settings.py and are loaded via DJANGO_SETTINGS_MODULE
# Vulture sees them as unused module-level assignments; they are not.
