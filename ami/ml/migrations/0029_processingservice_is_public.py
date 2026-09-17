"""
``ProcessingService.is_public`` marks a service as available to every project,
not just the ones in its ``projects`` M2M. Schema only: unlike TaxaList, an
existing zero-project service does not become public here — it stays visible
to superusers only until someone explicitly opts it in.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0028_normalize_empty_endpoint_url_to_null"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="processingservice",
            options={
                "permissions": [
                    ("manage_public_processingservice", "Can create, edit and delete public processing services")
                ],
                "verbose_name": "Processing Service",
                "verbose_name_plural": "Processing Services",
            },
        ),
        migrations.AddField(
            model_name="processingservice",
            name="is_public",
            field=models.BooleanField(
                default=False,
                help_text="Public processing services are available to every project, not just the ones in 'projects'.",
            ),
        ),
    ]
