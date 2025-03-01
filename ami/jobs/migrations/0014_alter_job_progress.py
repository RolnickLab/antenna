# Generated by Django 4.2.10 on 2024-12-17 20:13

import ami.jobs.models
from django.db import migrations
import django_pydantic_field.fields


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0013_add_job_logs"),
    ]

    operations = [
        migrations.AlterField(
            model_name="job",
            name="progress",
            field=django_pydantic_field.fields.PydanticSchemaField(
                config=None,
                default={"errors": [], "logs": [], "stages": [], "summary": {"progress": 0.0, "status": "CREATED"}},
                schema=ami.jobs.models.JobProgress,
            ),
        ),
    ]
