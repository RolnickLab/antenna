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
        name="celery.check_processing_services_online",
        task="ami.ml.tasks.check_processing_services_online",
        crontab=crontab_schedule,
    )


def delete_periodic_task(apps, schema_editor):
    # Delete the task if rolling back
    PeriodicTask.objects.filter(name="celery.check_processing_services_online").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0017_alter_algorithm_unique_together"),
    ]

    operations = [
        migrations.RunPython(create_periodic_task, delete_periodic_task),
    ]
