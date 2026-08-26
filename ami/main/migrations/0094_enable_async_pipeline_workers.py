"""
Turn on the ``async_pipeline_workers`` feature flag for every existing project.

This rolls out async ML processing (workers that pull tasks from the NATS queue
instead of the synchronous push API) to all projects at once. New projects keep
whatever the model default is at creation time; this migration only updates rows
that exist at deploy time.

The flag lives inside the ``feature_flags`` JSONB column (a ``ProjectFeatureFlags``
pydantic model). The update toggles only the one key server-side with ``jsonb_set``
rather than reading each project's JSON into Python, mutating it, and writing the
whole value back. Doing it in place leaves the other feature flags untouched even
if another process changes one of them during the deploy, and it runs as a single
statement instead of one save per row. The reverse flips the flag back off for
every project — a blanket disable. It does not restore per-project values from
before the rollout: some projects may have had the flag enabled individually
beforehand, so the reverse returns every project to the off state rather than to
its prior value.
"""

from django.db import migrations


def _set_async_pipeline_workers(apps, schema_editor, *, enabled):
    Project = apps.get_model("main", "Project")
    table = schema_editor.connection.ops.quote_name(Project._meta.db_table)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE {table}
            SET feature_flags = jsonb_set(
                COALESCE(feature_flags, '{{}}'::jsonb),
                '{{async_pipeline_workers}}',
                to_jsonb(%s::boolean),
                true
            )
            WHERE COALESCE((feature_flags ->> 'async_pipeline_workers')::boolean, false)
                  IS DISTINCT FROM %s
            """,
            [enabled, enabled],
        )


def enable_async_pipeline_workers(apps, schema_editor):
    _set_async_pipeline_workers(apps, schema_editor, enabled=True)


def disable_async_pipeline_workers(apps, schema_editor):
    _set_async_pipeline_workers(apps, schema_editor, enabled=False)


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0093_occurrence_project_score_index"),
    ]

    operations = [
        migrations.RunPython(enable_async_pipeline_workers, disable_async_pipeline_workers),
    ]
