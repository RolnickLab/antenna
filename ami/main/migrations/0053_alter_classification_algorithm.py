# Generated by Django 4.2.10 on 2025-02-10 06:31

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0052_merge_20250207_1012"),
    ]

    operations = [
        migrations.AlterField(
            model_name="classification",
            name="algorithm",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="classifications",
                to="ml.algorithm",
            ),
        ),
    ]
