"""
Backfill the denormalized ``SourceImageCollection`` count columns added in
0085.

Split from the schema migration on purpose: this is the slow step on
production-sized M2M tables. ``atomic = False`` lets the UPDATE run outside a
single transaction, and the UPDATE writes absolute computed values (not
deltas) so it is idempotent — safe to re-run if interrupted. Collections with
no images keep the column ``default=0`` from 0085 (the GROUP BY only emits
rows for collections that have images).

``with_det`` checks for a valid (non-null / non-empty) detection bbox to match
the runtime ``NULL_DETECTIONS_FILTER`` semantics in ``ami/main/models.py``.
"""

from django.db import migrations


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


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("main", "0085_denormalize_sourceimagecollection_counts"),
    ]

    operations = [
        migrations.RunPython(backfill_counts, reverse_noop),
    ]
