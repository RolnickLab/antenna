# A database that applied an earlier draft of 0102 has a vector(2048) column, which rejects
# vectors of any other length. Dropping the length is a no-op where the column already has none.
# Django's state already matches, so this only touches the database. See #1417.

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0103_occurrence_history"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE main_detectionembedding ALTER COLUMN vector TYPE vector",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
