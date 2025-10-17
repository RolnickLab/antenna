from django.db import migrations
from django_celery_beat.models import PeriodicTask, CrontabSchedule


def create_periodic_task(apps, schema_editor):
    crontab_schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="*/5",  # Every 5 minutes
        hour="*",  # Every hour
        day_of_week="*",  # Every day
        day_of_month="*",  # Every day of month
        month_of_year="*",  # Every month
    )

    PeriodicTask.objects.get_or_create(
        name="celery.check_dangling_ml_jobs",
        task="ami.ml.tasks.check_dangling_ml_jobs",
        crontab=crontab_schedule,
    )


def delete_periodic_task(apps, schema_editor):
    # Delete the task if rolling back
    PeriodicTask.objects.filter(name="celery.check_dangling_ml_jobs").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0022_alter_pipeline_default_config"),
    ]

    operations = [
        migrations.RunPython(create_periodic_task, delete_periodic_task),
    ]
