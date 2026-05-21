from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0083_dedupe_taxalist_names"),
    ]

    # AddIndexConcurrently requires running outside a transaction.
    atomic = False

    operations = [
        AddIndexConcurrently(
            model_name="detection",
            index=models.Index(
                fields=["occurrence", "-timestamp"],
                name="detection_occurrence_ts_desc",
            ),
        ),
    ]
