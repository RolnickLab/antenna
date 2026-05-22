from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    """Add the index backing the project "recent captures" sort.

    SourceImage is large in production (tens of millions of rows), so the index
    is built CONCURRENTLY to avoid taking a write lock during deploy, which
    requires a non-atomic migration.

    A concurrent build on a table this size can exceed a configured
    ``statement_timeout`` (development sets 30s, see ``config/settings/local.py``;
    a production role may set one too). ``CREATE INDEX CONCURRENTLY`` runs as a
    single statement subject to that timeout, so clear it for this connection
    before building.
    """

    atomic = False

    dependencies = [
        ("main", "0085_project_activity_sort_indexes"),
    ]

    operations = [
        # Runtime SET overrides the startup "-c statement_timeout" option and
        # persists for the rest of this (non-atomic) migration's connection.
        migrations.RunSQL(
            sql="SET statement_timeout = 0;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        AddIndexConcurrently(
            model_name="sourceimage",
            index=models.Index(fields=["project", "-timestamp"], name="main_source_proj_ts_desc_idx"),
        ),
    ]
