from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    """Index the classification's link to its algorithm result, which deleting a result looks up.

    Partial, because pipeline classifications never have a result, so the index stays small.
    Built CONCURRENTLY on this large table, which needs a non-atomic migration; see 0093 for
    why the statement timeout is cleared and restored around the build.
    """

    atomic = False

    dependencies = [
        ("main", "0098_classification_algorithm_result"),
    ]

    operations = [
        migrations.RunSQL(
            sql="SET statement_timeout = 0;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        AddIndexConcurrently(
            model_name="classification",
            index=models.Index(
                condition=models.Q(algorithm_result__isnull=False),
                fields=["algorithm_result"],
                name="cls_algorithm_result_idx",
            ),
        ),
        migrations.RunSQL(
            sql="RESET statement_timeout;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
