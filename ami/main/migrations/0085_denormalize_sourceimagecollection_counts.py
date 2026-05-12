"""
Denormalize three counts onto ``SourceImageCollection`` so the list endpoint
reads them in O(1) instead of running 3 correlated count subqueries per row.

Backfill uses a single GROUP BY over the M2M with FILTER clauses to compute
all three counts in one pass. ``with_det`` checks for a valid (non-null /
non-empty) detection bbox to match the runtime
``NULL_DETECTIONS_FILTER`` semantics in ``ami/main/models.py``.

``atomic = False`` so the long UPDATE can run outside a single transaction
on production-sized M2M tables.
"""

from django.db import migrations, models


def backfill_counts(apps, schema_editor):
    schema_editor.execute(
        """
        UPDATE main_sourceimagecollection sc
        SET source_images_count = c.total,
            source_images_processed_count = c.processed,
            source_images_with_detections_count = c.with_det
        FROM (
            SELECT msci.sourceimagecollection_id AS coll_id,
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE EXISTS (
                        SELECT 1 FROM main_detection d
                        WHERE d.source_image_id = si.id
                    )
                ) AS processed,
                COUNT(*) FILTER (
                    WHERE EXISTS (
                        SELECT 1 FROM main_detection d
                        WHERE d.source_image_id = si.id
                          AND d.bbox IS NOT NULL
                          AND d.bbox::text <> '[]'
                    )
                ) AS with_det
            FROM main_sourceimagecollection_images msci
            INNER JOIN main_sourceimage si ON si.id = msci.sourceimage_id
            GROUP BY msci.sourceimagecollection_id
        ) c
        WHERE sc.id = c.coll_id;
        """
    )
    # Collections with no images: paginated SELECTs returned 0 via Coalesce; keep
    # them populated rather than NULL so the column reads stay consistent.
    schema_editor.execute(
        """
        UPDATE main_sourceimagecollection
        SET source_images_count = 0,
            source_images_processed_count = 0,
            source_images_with_detections_count = 0
        WHERE source_images_count IS NULL;
        """
    )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

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
        migrations.RunPython(backfill_counts, reverse_noop),
    ]
