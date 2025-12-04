# Generated manually for periodic job status checking

from django.db import migrations


def create_periodic_task(apps, schema_editor):
    """Create periodic task to check unfinished jobs every 3 minutes."""
    try:
        from django_celery_beat.models import IntervalSchedule, PeriodicTask

        interval_schedule, _ = IntervalSchedule.objects.get_or_create(
            every=3,
            period=IntervalSchedule.MINUTES,
        )

        PeriodicTask.objects.get_or_create(
            name="jobs.check_incomplete_jobs",
            defaults={
                "task": "ami.jobs.tasks.check_incomplete_jobs",
                "interval": interval_schedule,
                "enabled": True,
                "description": "Check status of unfinished jobs and update if tasks disappeared",
            },
        )
    except Exception as e:
        print(f"Warning: Could not create periodic task: {e}")
        print("You may need to create it manually in the Django admin or via shell.")


def delete_periodic_task(apps, schema_editor):
    """Delete the periodic task if rolling back."""
    try:
        from django_celery_beat.models import PeriodicTask

        PeriodicTask.objects.filter(name="jobs.check_incomplete_jobs").delete()
    except Exception as e:
        print(f"Warning: Could not delete periodic task: {e}")


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0019_job_last_checked_at"),
    ]

    operations = [
        migrations.RunPython(create_periodic_task, delete_periodic_task),
    ]
