from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0018_advisorconversation_advisormessage_advisorrun_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="advisorrun",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("running", "Running"),
                    ("waiting_for_user", "Waiting for user"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                    ("canceled", "Canceled"),
                ],
                default="pending",
                max_length=16,
            ),
        ),
    ]
