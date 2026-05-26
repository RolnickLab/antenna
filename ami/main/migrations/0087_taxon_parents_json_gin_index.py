from django.db import migrations


class Migration(migrations.Migration):
    """
    GIN index on Taxon.parents_json to support the hierarchical (descendant) taxon
    filters that issue a literal `parents_json @> [{"id": <id>}]` containment: the
    occurrence-list `taxon=<id>` filter (CustomOccurrenceDeterminationFilter) and the
    project default-taxa filter (build_occurrence_default_filters_q). The index applies
    to these because the right-hand side is a constant.

    Note it does NOT back the #1316 per-taxon verification / agreement rollup: that is
    computed in a single Python pass over the (sparse) verified-occurrence set rather
    than a correlated subquery, because a containment whose RHS is an OuterRef can't use
    the index. See TaxonViewSet.add_verification_data.

    CREATE INDEX CONCURRENTLY can't run inside a transaction, so this migration is
    non-atomic. IF NOT EXISTS keeps it safe to co-exist with the same index if it lands
    separately via the #1307 follow-up.
    """

    atomic = False

    dependencies = [
        ("main", "0086_sourceimage_recent_capture_index"),
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
