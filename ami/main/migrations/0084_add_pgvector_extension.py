from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0083_dedupe_taxalist_names"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS vector;",
            reverse_sql="DROP EXTENSION IF EXISTS vector;",
        ),
    ]
