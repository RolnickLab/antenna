"""
Rewords ProcessingService.is_public's help text: "available to every project"
overstated it — job dispatch, the async heartbeat, and the pipeline views still
filter by project link regardless of is_public. Schema-only, no data change.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0029_processingservice_is_public"),
    ]

    operations = [
        migrations.AlterField(
            model_name="processingservice",
            name="is_public",
            field=models.BooleanField(
                default=False,
                help_text="Public services are shown to every project, not just the ones linked via 'projects'; running a job still requires the service to be linked to the project.",
            ),
        ),
    ]
