from django.db import migrations, models
from django_celery_beat.models import PeriodicTask, IntervalSchedule


def create_periodic_task(apps, schema_editor):
    """Create periodic task to check unfinished jobs every 3 minutes."""
    interval_schedule, _ = IntervalSchedule.objects.get_or_create(
        every=3,
        period=IntervalSchedule.MINUTES,
    )

    PeriodicTask.objects.get_or_create(
        name="jobs.check_unfinished_jobs",
        task="ami.jobs.tasks.check_unfinished_jobs",
        interval=interval_schedule,
        defaults={
            "enabled": True,
            "description": "Check status of all unfinished jobs and update if tasks have disappeared",
        },
    )


def delete_periodic_task(apps, schema_editor):
    """Delete the periodic task if rolling back."""
    PeriodicTask.objects.filter(name="jobs.check_unfinished_jobs").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0017_alter_job_logs_alter_job_progress"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="last_checked_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Last time job status was checked",
                null=True,
            ),
        ),
        migrations.RunPython(create_periodic_task, delete_periodic_task),
    ]
