from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    """Index the job columns added in 0096 for the ``?job=`` occurrence filter.

    Each index covers what the filter reads (job and occurrence, or job and detection),
    so the filter is answered from the index alone. Both are partial: rows written before
    jobs were recorded have no job and are left out, which keeps the build short and the
    index small. Detection and classification are the largest tables, so the indexes are
    built CONCURRENTLY, which needs a non-atomic migration; see 0093 for why the statement
    timeout is cleared and restored around the build.
    """

    atomic = False

    dependencies = [
        ("main", "0096_detection_and_classification_job"),
    ]

    operations = [
        migrations.RunSQL(
            sql="SET statement_timeout = 0;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        AddIndexConcurrently(
            model_name="detection",
            index=models.Index(
                condition=models.Q(job__isnull=False),
                fields=["job", "occurrence"],
                name="det_job_occurrence_idx",
            ),
        ),
        AddIndexConcurrently(
            model_name="classification",
            index=models.Index(
                condition=models.Q(job__isnull=False),
                fields=["job", "detection"],
                name="cls_job_detection_idx",
            ),
        ),
        migrations.RunSQL(
            sql="RESET statement_timeout;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
