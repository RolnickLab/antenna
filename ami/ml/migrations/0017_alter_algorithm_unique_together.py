# Generated by Django 4.2.10 on 2025-02-06 02:50

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0016_merge_20250117_2101"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="algorithm",
            unique_together={("name", "version")},
        ),
    ]
