"""
We have had the terminal field in the Classification model for a while now, but we have not been using it.
Now we need to filter classifications based on this field, so we need to update the existing classifications
where a binary / intermediate classification was used.
"""

import logging

from django.db import migrations, models

logger = logging.getLogger(__name__)


MOTH_NONMOTH_LABELS = [
    "moth",
    "non-moth",
    "nonmoth",
]


def update_classification_labels(apps, schema_editor):
    Classification = apps.get_model("main", "Classification")

    # Create regex pattern from labels to make a case-insensitive match
    pattern = r"^(" + "|".join(MOTH_NONMOTH_LABELS) + ")$"

    # Log number of updated classifications
    logger.info(f"\nUpdating classifications with labels matching pattern: {pattern} (case insensitive)")

    # Update only matching classifications
    updated = Classification.objects.filter(taxon__name__iregex=pattern).update(terminal=False)

    logger.info(f"\nUpdated {updated} moth/non-moth classifications to terminal=False")


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0014_rename_model_keys"),
    ]

    operations = [
        migrations.RunPython(
            update_classification_labels,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
