from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0078_classification_applied_to"),
    ]

    operations = [
        migrations.AddField(
            model_name="deployment",
            name="time_zone",
            field=models.CharField(
                default=settings.TIME_ZONE,
                help_text="IANA time zone for this deployment (e.g., 'America/Los_Angeles'). Used as metadata for interpreting local timestamps.",
                max_length=64,
            ),
        ),
    ]
