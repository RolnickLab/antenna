"""
Add ``TaxaList.is_public`` and backfill it for existing rows.

A TaxaList with no project was previously treated as an ad hoc "global" list by
convention (see ``get_or_create_for_project``); this migration makes that status an
explicit, queryable field instead. Every existing zero-project list becomes public,
except a per-algorithm category-map list (name starting with "Taxa returned by"),
which stays hidden as it is today — those lists are an internal bookkeeping detail,
not something meant for every project to browse or attach.

``projects`` becomes optional (``blank=True``) since a public list no longer needs
a project association to exist.
"""

from django.db import migrations, models
from django.db.models import Count


def backfill_is_public(apps, schema_editor):
    TaxaList = apps.get_model("main", "TaxaList")
    zero_project_lists = TaxaList.objects.annotate(project_count=Count("projects")).filter(project_count=0)
    zero_project_lists.exclude(name__startswith="Taxa returned by").update(is_public=True)


def reverse_noop(apps, schema_editor):
    # Not reversible: we don't track which rows were public before this migration.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0095_grant_sync_deployment_to_mldatamanager"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="taxalist",
            options={
                "ordering": ["-created_at"],
                "permissions": [("manage_public_taxalist", "Can create, edit and delete public taxa lists")],
                "verbose_name_plural": "Taxa Lists",
            },
        ),
        migrations.AddField(
            model_name="taxalist",
            name="is_public",
            field=models.BooleanField(
                default=False,
                help_text="Public lists are available to every project, not just the ones in 'projects'.",
            ),
        ),
        migrations.AlterField(
            model_name="taxalist",
            name="projects",
            field=models.ManyToManyField(blank=True, related_name="taxa_lists", to="main.project"),
        ),
        migrations.RunPython(backfill_is_public, reverse_noop),
    ]
