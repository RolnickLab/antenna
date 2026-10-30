from django.db import migrations

TASK_NAME = "ml.export_training_data_snapshot"


def create_periodic_task(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    # Sundays at 03:00 server time.
    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="3",
        day_of_week="0",
        day_of_month="*",
        month_of_year="*",
    )
    PeriodicTask.objects.get_or_create(
        name=TASK_NAME,
        defaults={
            "task": "ami.ml.tasks.export_training_data_snapshot",
            "crontab": schedule,
            # Off until an admin turns it on: each run writes files to storage.
            "enabled": False,
            "description": "Export the verified species data of opted-in projects for platform-wide training.",
        },
    )


def delete_periodic_task(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0033_training_data_snapshot"),
        ("django_celery_beat", "0018_improve_crontab_helptext"),
    ]

    operations = [
        migrations.RunPython(create_periodic_task, delete_periodic_task),
    ]
