import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Add the column that links a detection to the one that follows it in a tracking sequence.

    Django would add this column together with a unique constraint and a foreign key in one
    statement, which takes a lock on the large detection table that blocks reads while the
    unique index is built. Here the column is added on its own: a nullable column without a
    default is a catalogue change that does not scan the table. Migration 0101 adds the unique
    constraint and the foreign key afterwards without blocking readers or writers.
    """

    dependencies = [
        ("main", "0099_classification_algorithm_result_index"),
    ]

    operations = [
        # Adding the column takes a brief exclusive lock. Give up rather than queue behind a long query on
        # the table, which would block every other query until it ends; rerun the migration if it gives up.
        migrations.RunSQL(sql="SET LOCAL lock_timeout = '10s';", reverse_sql=migrations.RunSQL.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="detection",
                    name="next_detection",
                    field=models.OneToOneField(
                        blank=True,
                        help_text="The detection that follows this one in the tracking sequence.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="previous_detection",
                        to="main.detection",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE "main_detection" ADD COLUMN "next_detection_id" bigint NULL;',
                    reverse_sql='ALTER TABLE "main_detection" DROP COLUMN "next_detection_id";',
                ),
            ],
        ),
    ]
