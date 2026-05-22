from django.db import migrations


class Migration(migrations.Migration):
    """
    GIN index on Taxon.parents_json to support hierarchical (descendant) rollup
    of the per-taxon verification / agreement counts added for issue #1316.

    Without it, Family- and Order-rank rows on large projects fall back to a
    seq-scan on the parents_json containment (`@>`) test and dominate query time.

    CREATE INDEX CONCURRENTLY can't run inside a transaction, so this migration
    is non-atomic. IF NOT EXISTS keeps it safe to co-exist with the same index if
    it lands separately via the #1307 follow-up.
    """

    atomic = False

    dependencies = [
        ("main", "0084_revoke_delete_job_from_roles"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS main_taxon_parents_json_gin_idx "
                "ON main_taxon USING gin (parents_json jsonb_path_ops);"
            ),
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS main_taxon_parents_json_gin_idx;",
        ),
    ]
