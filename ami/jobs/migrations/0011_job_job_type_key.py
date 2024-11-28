# Generated by Django 4.2.10 on 2024-11-11 15:17

from django.db import migrations, models


# Add method to set job_type_key based on inferred job type
def set_job_type_key(apps, schema_editor):
    from ami.jobs.models import get_job_type_by_inferred_key, UnknownJobType

    Job = apps.get_model("jobs", "Job")
    for job in Job.objects.all():
        inferred_key = get_job_type_by_inferred_key(job)
        if inferred_key:
            job.job_type_key = inferred_key.key
        else:
            job.job_type_key = UnknownJobType.key
        job.save()


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0010_job_limit_job_shuffle"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="job_type_key",
            field=models.CharField(
                choices=[
                    ("ml", "ML pipeline"),
                    ("populate_captures_collection", "Populate captures collection"),
                    ("data_storage_sync", "Data storage sync"),
                    ("unknown", "Unknown"),
                ],
                default="unknown",
                max_length=255,
                verbose_name="Job Type",
            ),
        ),
        migrations.RunPython(set_job_type_key, reverse_code=migrations.RunPython.noop),
    ]
