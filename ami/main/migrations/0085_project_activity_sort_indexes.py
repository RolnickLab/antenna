from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    """Add the composite index that backs the project "recent identifications" sort.

    Occurrence is large in production, so the index is built CONCURRENTLY to avoid
    taking a write lock during deploy. This requires a non-atomic migration.

    Building the index can take longer than a configured ``statement_timeout``
    (development sets 30s, see ``config/settings/local.py``; a production role may
    set one too). ``CREATE INDEX CONCURRENTLY`` runs as a single statement and is
    subject to that timeout, so we clear it for this connection before building,
    then RESET it afterwards. The SET is session-scoped and this migration is
    non-atomic, so without the trailing RESET later migrations sharing the
    connection would inherit ``timeout=0`` and silently lose the safeguard.
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
            model_name="occurrence",
            index=models.Index(fields=["project", "-updated_at"], name="occur_proj_updated_desc_idx"),
        ),
        # Restore the session default so the disabled timeout does not leak into
        # later migrations executed on the same (non-atomic) connection.
        migrations.RunSQL(
            sql="RESET statement_timeout;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
