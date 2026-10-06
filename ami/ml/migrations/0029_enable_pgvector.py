# First install of the pgvector extension, which stores feature vectors (DetectionEmbedding).
#
# The extension package must already be installed on the PostgreSQL server (for example
# the postgresql-16-pgvector package); CREATE EXTENSION only registers it in this database.
# The check below runs before any SQL so a missing or outdated package stops the deploy
# with one clear message instead of a Postgres error about a control file. See #1453.

from django.db import migrations

MINIMUM_VERSION = (0, 8)


def check_pgvector_is_installed(apps, schema_editor):
    """Stop before any SQL runs unless the server offers pgvector 0.8 or later.

    ``halfvec`` needs 0.7; 0.8 adds the iterative index scans a nearest-neighbour index
    will rely on, so a first install starts there.
    """
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT default_version FROM pg_available_extensions WHERE name = 'vector'")
        row = cursor.fetchone()
    minimum = ".".join(str(part) for part in MINIMUM_VERSION)
    if row is None:
        raise RuntimeError(
            f"The pgvector extension is not installed on this PostgreSQL server. Install pgvector {minimum} "
            "or later (for example the postgresql-16-pgvector package) on every database server, then "
            "run this migration again."
        )
    (version,) = row
    try:
        parsed = tuple(int(part) for part in version.split(".")[:2])
    except ValueError:
        parsed = ()
    if parsed < MINIMUM_VERSION:
        raise RuntimeError(
            f"pgvector {minimum} or later must be installed on this PostgreSQL server; found {version}. "
            "Upgrade the pgvector package on every database server, then run this migration again."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0028_normalize_empty_endpoint_url_to_null"),
    ]

    operations = [
        migrations.RunPython(check_pgvector_is_installed, migrations.RunPython.noop),
        migrations.RunSQL(
            # ALTER ... UPDATE is a no-op on a fresh install. It only matters for a development
            # database where an experiment already created an older version of the extension.
            sql="CREATE EXTENSION IF NOT EXISTS vector; ALTER EXTENSION vector UPDATE;",
            # The extension may be shared with other databases on the server, and dropping it can
            # be restricted in hosted environments, so the reverse leaves it in place.
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
