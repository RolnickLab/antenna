from django.db import migrations


def create_periodic_tasks(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="*/15",
        hour="*",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
    )
    PeriodicTask.objects.get_or_create(
        name="jobs.health_check",
        defaults={
            "task": "ami.jobs.tasks.jobs_health_check",
            "crontab": schedule,
            "description": (
                "Umbrella job-health checks: stale-job reconciler plus a NATS "
                "consumer snapshot for each running async_api job."
            ),
        },
    )


def delete_periodic_tasks(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="jobs.health_check").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0019_job_dispatch_mode"),
        ("django_celery_beat", "0018_improve_crontab_helptext"),
    ]

    operations = [
        migrations.RunPython(create_periodic_tasks, delete_periodic_tasks),
    ]
