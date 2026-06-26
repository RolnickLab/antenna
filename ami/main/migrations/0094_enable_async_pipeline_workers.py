"""
Turn on the ``async_pipeline_workers`` feature flag for every existing project.

This rolls out async ML processing (workers that pull tasks from the NATS queue
instead of the synchronous push API) to all projects at once. New projects keep
the model default of ``False`` until they are opted in separately; this migration
only updates rows that exist at deploy time.

The flag lives inside the ``feature_flags`` JSONB column (a ``ProjectFeatureFlags``
pydantic model). We read each project's flags through the historical model, set the
one boolean, and write it back. The reverse flips the flag back off for every
project — a blanket disable. It does not restore per-project values from before the
rollout, because the field default is ``False`` and this is the first global enable,
so no project is expected to have been ``True`` beforehand.
"""

from django.db import migrations


def enable_async_pipeline_workers(apps, schema_editor):
    Project = apps.get_model("main", "Project")
    for project in Project.objects.all():
        flags = project.feature_flags
        if not flags.async_pipeline_workers:
            flags.async_pipeline_workers = True
            project.feature_flags = flags
            project.save(update_fields=["feature_flags"])


def disable_async_pipeline_workers(apps, schema_editor):
    Project = apps.get_model("main", "Project")
    for project in Project.objects.all():
        flags = project.feature_flags
        if flags.async_pipeline_workers:
            flags.async_pipeline_workers = False
            project.feature_flags = flags
            project.save(update_fields=["feature_flags"])


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0093_occurrence_project_score_index"),
    ]

    operations = [
        migrations.RunPython(enable_async_pipeline_workers, disable_async_pipeline_workers),
    ]
