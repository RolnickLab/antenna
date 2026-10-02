# Deleting a station keeps its jobs, since the outputs they wrote restrict deleting them.
# State only: Django applies on_delete in Python, so the database is unchanged.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0023_alter_job_job_type_key"),
    ]

    operations = [
        migrations.AlterField(
            model_name="job",
            name="deployment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="jobs",
                to="main.deployment",
            ),
        ),
    ]
