import ami.jobs.models
import django_pydantic_field.fields
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0021_joblog"),
    ]

    operations = [
        migrations.AlterField(
            model_name="job",
            name="logs",
            field=django_pydantic_field.fields.PydanticSchemaField(
                config=None,
                default=ami.jobs.models.JobLogs,
                help_text="DEPRECATED: read-only fallback for pre-#1259 jobs. Use the JobLog table for new writes.",
                schema=ami.jobs.models.JobLogs,
            ),
        ),
    ]
