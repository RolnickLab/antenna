"""
Rename duplicate TaxaList rows so that (name, scope) is unique.

Scope is either "global" (TaxaList with no project associations) or an individual
project. Within each scope, the oldest TaxaList keeps its name; later rows get a
" (duplicate N)" suffix, globally unique.

This migration does not merge taxa from duplicate lists — it only renames them so
that the MultipleObjectsReturned paths in TaxaList.objects.get_or_create_for_project
stop firing. Operators can review the renamed rows and merge/delete manually.
"""

from collections import defaultdict

from django.db import migrations


def dedupe_taxa_list_names(apps, schema_editor):
    TaxaList = apps.get_model("main", "TaxaList")

    # Group TaxaLists by (name, scope). For project-scoped lists, a single list can
    # participate in multiple (name, project) groups if it's attached to multiple projects.
    groups: dict[tuple[str, object], list[int]] = defaultdict(list)
    for tl in TaxaList.objects.all().order_by("created_at").prefetch_related("projects"):
        project_ids = list(tl.projects.values_list("id", flat=True))
        if not project_ids:
            groups[(tl.name, "global")].append(tl.pk)
        else:
            for pid in project_ids:
                groups[(tl.name, pid)].append(tl.pk)

    # A list needs renaming if it's not the oldest in any group it participates in.
    to_rename: set[int] = set()
    for pks in groups.values():
        if len(pks) > 1:
            # pks is already sorted by created_at because we ordered the outer query.
            for pk in pks[1:]:
                to_rename.add(pk)

    if not to_rename:
        return

    existing_names = set(TaxaList.objects.values_list("name", flat=True))
    # Process in created_at order so numbering is stable and predictable.
    renames_qs = TaxaList.objects.filter(pk__in=to_rename).order_by("created_at")
    for lst in renames_qs:
        base = lst.name
        i = 2
        while True:
            candidate = f"{base} (duplicate {i})"
            if candidate not in existing_names:
                lst.name = candidate
                lst.save(update_fields=["name"])
                existing_names.add(candidate)
                break
            i += 1


def reverse_noop(apps, schema_editor):
    # Not reversible: we don't track the original names, and renames are idempotent
    # enough that re-running forward is safe if needed.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0082_add_taxalist_permissions"),
    ]

    operations = [
        migrations.RunPython(dedupe_taxa_list_names, reverse_noop),
    ]
