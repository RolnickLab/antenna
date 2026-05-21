from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    """Add composite indexes that back the project "recent activity" sort options.

    Both tables are large in production (SourceImage in the tens of millions),
    so the indexes are built CONCURRENTLY to avoid taking a write lock during
    deploy. This requires a non-atomic migration.

    Building these indexes can take longer than a configured ``statement_timeout``
    (development sets 30s, see ``config/settings/local.py``; a production role may
    set one too). ``CREATE INDEX CONCURRENTLY`` runs as a single statement and is
    subject to that timeout, so we clear it for this connection before building.
    """

    atomic = False

    dependencies = [
        ("main", "0084_revoke_delete_job_from_roles"),
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
        AddIndexConcurrently(
            model_name="occurrence",
            index=models.Index(fields=["project", "-updated_at"], name="occur_proj_updated_desc_idx"),
        ),
    ]
