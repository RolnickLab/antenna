from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    """Index the occurrence sizes added in 0098 for the size filters and size sorting.

    The occurrence table is large, so the indexes are built CONCURRENTLY, which needs a
    non-atomic migration; see 0093 for why the statement timeout is cleared around the build.
    """

    atomic = False

    dependencies = [
        ("main", "0098_occurrence_size_and_deployment_calibration"),
    ]

    operations = [
        migrations.RunSQL(
            sql="SET statement_timeout = 0;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        AddIndexConcurrently(
            model_name="occurrence",
            index=models.Index(fields=["project", "relative_length"], name="occur_proj_rel_length"),
        ),
        AddIndexConcurrently(
            model_name="occurrence",
            index=models.Index(fields=["project", "length_mm"], name="occur_proj_length_mm"),
        ),
        migrations.RunSQL(
            sql="RESET statement_timeout;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
