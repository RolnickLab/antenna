from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0083_dedupe_taxalist_names"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS vector;",
            # No-op on reverse: the extension may be shared with other features/databases,
            # and dropping it can be restricted in some hosted environments.
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
