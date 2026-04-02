from __future__ import annotations

from django.db import migrations, models

FIXED_CATEGORIES = ["Housing & Utilities", "Debt Payment"]
SAVINGS_CATEGORIES = ["Savings & Investments"]


def set_expense_types(apps, schema_editor):
    del schema_editor
    Category = apps.get_model("core", "Category")
    Category.objects.filter(name__in=FIXED_CATEGORIES).update(expense_type="fixed")
    Category.objects.filter(name__in=SAVINGS_CATEGORIES).update(expense_type="savings_transfer")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0013_csvmappingprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="expense_type",
            field=models.CharField(
                choices=[("fixed", "Fixed"), ("variable", "Variable"), ("savings_transfer", "Savings Transfer")],
                default="variable",
                max_length=17,
            ),
        ),
        migrations.RunPython(set_expense_types, migrations.RunPython.noop),
    ]
