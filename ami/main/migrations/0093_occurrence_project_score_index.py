from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    """Add the index backing the default occurrence list sort.

    The occurrence list endpoint is scoped to a project and ordered by
    ``-determination_score`` (the model default ``Meta.ordering``). Without a
    matching index the planner sorts the whole project's occurrences on every
    page request, which becomes an on-disk merge sort on large projects.

    Occurrence is large in production (over a million rows), so the index is
    built CONCURRENTLY to avoid taking a write lock during deploy, which
    requires a non-atomic migration. See 0086 for the same pattern and the
    reason the statement timeout is cleared and restored around the build.

    The column order is ``DESC`` (Postgres ``NULLS FIRST``) to match the SQL the
    ORM emits for ``ORDER BY determination_score DESC`` exactly; a ``NULLS LAST``
    index would not serve that ordering when the result set contains rows with a
    null ``determination_score``.
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
            model_name="occurrence",
            index=models.Index(fields=["project", "-determination_score"], name="occur_proj_score_desc_idx"),
        ),
        # Restore the session default so the disabled timeout does not leak into
        # later migrations executed on the same (non-atomic) connection.
        migrations.RunSQL(
            sql="RESET statement_timeout;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
