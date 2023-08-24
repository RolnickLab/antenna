# Generated by Django 4.2.2 on 2023-08-24 03:01

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0027_deployment_data_source_total_files_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="sourceimage",
            constraint=models.UniqueConstraint(
                fields=("deployment", "timestamp", "path"), name="unique_deployment_timestamp_path"
            ),
        ),
    ]