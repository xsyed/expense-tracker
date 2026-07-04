from __future__ import annotations

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def clear_old_advisor_memory(apps: object, _schema_editor: object) -> None:
    advisor_memory = apps.get_model("core", "AdvisorMemory")
    advisor_memory.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0019_advisorrun_waiting_for_user"),
    ]

    operations = [
        migrations.RunPython(clear_old_advisor_memory, migrations.RunPython.noop),
        migrations.DeleteModel(name="AdvisorMemorySuggestion"),
        migrations.AlterUniqueTogether(name="advisormemory", unique_together=set()),
        migrations.RemoveField(model_name="advisormemory", name="key"),
        migrations.RemoveField(model_name="advisormemory", name="source"),
        migrations.RemoveField(model_name="advisormemory", name="value"),
        migrations.AddField(
            model_name="advisormemory",
            name="content",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="advisormemory",
            name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="advisor_memory",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterModelOptions(
            name="advisormemory",
            options={
                "ordering": ["user__email"],
                "verbose_name": "advisor memory",
                "verbose_name_plural": "advisor memories",
            },
        ),
    ]
