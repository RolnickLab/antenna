# First install of the pgvector extension, which stores feature vectors (DetectionEmbedding).
#
# The extension package must already be installed on the PostgreSQL server (for example
# the postgresql-16-pgvector package); CREATE EXTENSION only registers it in this database.
# The check below runs before any SQL so a missing or outdated package stops the deploy
# with one clear message instead of a Postgres error about a control file. See #1462.

from django.db import migrations

MINIMUM_VERSION = (0, 8)


def _parse_version(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split(".")[:2])
    except ValueError:
        return ()


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
    if _parse_version(version) < MINIMUM_VERSION:
        raise RuntimeError(
            f"pgvector {minimum} or later must be installed on this PostgreSQL server; found {version}. "
            "Upgrade the pgvector package on every database server, then run this migration again."
        )


def update_pgvector_if_older(apps, schema_editor):
    """Upgrade an extension an earlier experiment created below 0.8; leave a current one alone.

    ``ALTER EXTENSION ... UPDATE`` requires owning the extension even when there is nothing to
    update, so running it unconditionally fails where an administrator created the extension.
    """
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        (version,) = cursor.fetchone()
        if _parse_version(version) < MINIMUM_VERSION:
            cursor.execute("ALTER EXTENSION vector UPDATE")


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0029_algorithm_result"),
    ]

    operations = [
        migrations.RunPython(check_pgvector_is_installed, migrations.RunPython.noop),
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS vector;",
            # The extension may be shared with other databases on the server, and dropping it can
            # be restricted in hosted environments, so the reverse leaves it in place.
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunPython(update_pgvector_if_older, migrations.RunPython.noop),
    ]
