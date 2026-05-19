"""
Add three denormalized count columns to ``SourceImageCollection`` so the list
endpoint reads them in O(1) instead of running 3 correlated count subqueries
per row.

Schema only. The backfill runs in the separate, non-atomic, re-runnable
migration ``0086_backfill_sourceimagecollection_counts`` so an interrupted
backfill on production-sized data cannot leave the schema half-applied
(columns added but migration unrecorded -> retry fails on duplicate column).

``AddField`` with a constant ``default`` is a metadata-only operation on
PostgreSQL 11+, so this is safe to run atomically even on large tables.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0084_revoke_delete_job_from_roles"),
    ]

    operations = [
        migrations.AddField(
            model_name="sourceimagecollection",
            name="source_images_count",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="sourceimagecollection",
            name="source_images_with_detections_count",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="sourceimagecollection",
            name="source_images_processed_count",
            field=models.IntegerField(default=0),
        ),
    ]
