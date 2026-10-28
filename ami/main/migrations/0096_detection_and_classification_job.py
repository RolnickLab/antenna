from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Record the job that created each detection and classification.

    Adding a nullable foreign key column is a catalogue change: Postgres does not scan
    the table, so the lock on these two large tables is held only briefly. The column
    is indexed in 0097, concurrently, so no index is built inside this transaction.
    """

    dependencies = [
        ("jobs", "0023_alter_job_job_type_key"),
        ("main", "0095_grant_sync_deployment_to_mldatamanager"),
    ]

    operations = [
        migrations.AddField(
            model_name="classification",
            name="job",
            field=models.ForeignKey(
                blank=True,
                db_index=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="classifications",
                to="jobs.job",
            ),
        ),
        migrations.AddField(
            model_name="detection",
            name="job",
            field=models.ForeignKey(
                blank=True,
                db_index=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="detections",
                to="jobs.job",
            ),
        ),
    ]
