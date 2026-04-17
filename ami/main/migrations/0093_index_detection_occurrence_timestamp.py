from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    """Add the composite index backing per-occurrence detection ordering.

    The index on Detection (occurrence_id, timestamp DESC) supports the
    Min/Max(detections__timestamp) aggregations on the occurrence list and the
    first/last appearance lookups, which otherwise sort a large detection row
    set after joining from occurrence.

    Detection is one of the largest tables in production, so the index is built
    CONCURRENTLY to avoid taking a write lock during deploy, which requires a
    non-atomic migration. A concurrent build on a table this size can exceed a
    configured ``statement_timeout`` (development sets 30s, see
    ``config/settings/local.py``; a production role may set one too).
    ``CREATE INDEX CONCURRENTLY`` runs as a single statement subject to that
    timeout, so clear it for this connection before building, then RESET it
    afterwards. The SET is session-scoped and this migration is non-atomic, so
    without the trailing RESET later migrations sharing the connection would
    inherit ``timeout=0`` and lose the safeguard.
    """

    atomic = False

    dependencies = [
        ("main", "0092_alter_sourceimage_checksum_and_more"),
    ]

    operations = [
        # Runtime SET overrides the startup "-c statement_timeout" option and
        # persists for the rest of this (non-atomic) migration's connection.
        migrations.RunSQL(
            sql="SET statement_timeout = 0;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        AddIndexConcurrently(
            model_name="detection",
            index=models.Index(
                fields=["occurrence", "-timestamp"],
                name="detection_occurrence_ts_desc",
            ),
        ),
        # Restore the session default so the disabled timeout does not leak into
        # later migrations executed on the same (non-atomic) connection.
        migrations.RunSQL(
            sql="RESET statement_timeout;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
