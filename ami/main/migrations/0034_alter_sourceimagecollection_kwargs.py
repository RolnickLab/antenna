# Generated by Django 4.2.2 on 2023-09-15 23:10

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0033_sourceimagecollection"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sourceimagecollection",
            name="kwargs",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Arguments passed to the sampling function",
                null=True,
                verbose_name="Arguments",
            ),
        ),
    ]
