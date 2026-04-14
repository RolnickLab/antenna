from django.db import migrations


def create_periodic_tasks(apps, schema_editor):
    from django_celery_beat.models import CrontabSchedule, PeriodicTask

    stale_schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="*/15",
        hour="*",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
    )
    PeriodicTask.objects.get_or_create(
        name="jobs.check_stale_jobs",
        defaults={
            "task": "ami.jobs.tasks.check_stale_jobs_task",
            "crontab": stale_schedule,
            "description": "Reconcile jobs stuck in running states past FAILED_CUTOFF_HOURS",
        },
    )

    stats_schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="*/5",
        hour="*",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
    )
    PeriodicTask.objects.get_or_create(
        name="jobs.log_running_async_job_stats",
        defaults={
            "task": "ami.jobs.tasks.log_running_async_job_stats",
            "crontab": stats_schedule,
            "description": "Log NATS consumer delivered/ack/pending stats for each running async_api job",
        },
    )


def delete_periodic_tasks(apps, schema_editor):
    from django_celery_beat.models import PeriodicTask

    PeriodicTask.objects.filter(
        name__in=["jobs.check_stale_jobs", "jobs.log_running_async_job_stats"],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0019_job_dispatch_mode"),
    ]

    operations = [
        migrations.RunPython(create_periodic_tasks, delete_periodic_tasks),
    ]
