# Generated by Django 4.2.2 on 2023-07-28 01:14

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0007_page"),
    ]

    operations = [
        migrations.AddField(
            model_name="page",
            name="published",
            field=models.BooleanField(default=False),
        ),
    ]
