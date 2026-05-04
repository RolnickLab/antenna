from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0020_schedule_job_monitoring_beat_tasks"),
    ]

    operations = [
        migrations.CreateModel(
            name="JobLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("level", models.CharField(max_length=20)),
                ("message", models.TextField()),
                ("context", models.JSONField(blank=True, default=dict)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="log_entries", to="jobs.job"
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-pk"],
                "indexes": [models.Index(fields=["job", "-created_at"], name="jobs_joblog_job_id_e4aa59_idx")],
            },
        ),
    ]
