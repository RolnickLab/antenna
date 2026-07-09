from django.db import migrations


def backfill_model_coverage(apps, schema_editor):
    """Populate Taxon.covered_by_algorithms / has_model_coverage for existing rows.

    Coverage is derived data and the columns added in 0095 default to empty / False,
    so without this backfill a fresh deploy (or an existing database gaining these
    fields) would report every taxon as not-model-covered until the
    refresh_taxon_model_coverage command is run by hand. A regional taxa list — and
    its dry-run preview — would then come back empty on a real region. Deriving from
    the runtime service keeps the backfill identical to how coverage is computed
    afterwards. A database with no algorithms is a no-op.
    """
    from ami.main.services.taxon_coverage import refresh_all_algorithm_coverage

    refresh_all_algorithm_coverage()


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0095_regional_taxa_lists"),
        ("ml", "0028_normalize_empty_endpoint_url_to_null"),
    ]

    operations = [
        migrations.RunPython(backfill_model_coverage, migrations.RunPython.noop),
    ]
