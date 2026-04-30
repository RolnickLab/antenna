import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0085_classification_features_2048"),
    ]

    operations = [
        migrations.AddField(
            model_name="detection",
            name="next_detection",
            field=models.OneToOneField(
                blank=True,
                help_text="The detection that follows this one in the tracking sequence.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="previous_detection",
                to="main.detection",
            ),
        ),
    ]
