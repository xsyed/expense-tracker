from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0014_category_expense_type"),
    ]

    operations = [
        migrations.DeleteModel(
            name="CSVUpload",
        ),
    ]
