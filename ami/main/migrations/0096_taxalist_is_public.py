"""
``TaxaList.is_public`` marks a list as available to every project, not just the
ones in its ``projects`` M2M. This backfills it: every existing list with no
project becomes public, except a "Taxa returned by <algorithm>" list — the
running set of taxa that algorithm has returned as a top prediction — which
stays non-public, since what a project should see or do with that list is
still undecided. ``projects`` becomes ``blank=True`` since a public list no
longer needs one.
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
