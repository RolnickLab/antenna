"""
Grant the existing ``sync_deployment`` permission to ``MLDataManager`` role
groups on projects that already exist.

``MLDataManager`` already holds ``run_data_storage_sync_job`` (it can run/retry a
sync job) but not ``sync_deployment`` (which gates *starting* a sync from a
station via ``POST /api/v2/deployments/<pk>/sync/`` and the bulk
``.../sync-all/`` action). This closes that gap so ML data managers can trigger
syncs, not only manage the resulting jobs. ``ProjectManager`` already has the
permission and is unaffected.

Permissions here are guardian **object-level** grants on each project, which is
what ``get_perms(user, project)`` and ``user.has_perm("sync_deployment",
project)`` read. Adding the permission only to ``group.permissions`` (a global
Django permission) is not enough — it would not appear in ``get_perms`` and the
Sync buttons / endpoint would stay inaccessible. So this migration mirrors
``create_roles_for_project``: it adds the global permission for parity and, more
importantly, creates the object-level ``GroupObjectPermission`` row per project.

New projects pick this up automatically through ``create_roles_for_project``
(``MLDataManager`` now includes the permission). A ``post_migrate`` signal
(``ami.main.apps`` → ``create_roles``) also re-syncs every project's role
permissions on migrate, so this backfill is belt-and-suspenders; it is kept so
the grant is explicit and self-contained rather than relying on that signal.

The ``sync_deployment`` permission itself is already defined on
``Project.Meta.permissions``, so there is no model/schema change here — only a
data backfill.
"""

from django.db import migrations
from django.db.models import Q


def _sync_permission(apps):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    try:
        project_ct = ContentType.objects.get(app_label="main", model="project")
    except ContentType.DoesNotExist:
        return None, None
    try:
        return Permission.objects.get(codename="sync_deployment", content_type=project_ct), project_ct
    except Permission.DoesNotExist:
        return None, None


def _project_pk_from_group(group):
    # Group names are "{project_pk}_{project_name}_{RoleName}"; the pk is the
    # immutable leading segment (the name can contain underscores).
    try:
        return int(group.name.split("_", 1)[0])
    except (ValueError, IndexError):
        return None


def grant_sync_to_mldatamanager(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    GroupObjectPermission = apps.get_model("guardian", "GroupObjectPermission")

    perm, project_ct = _sync_permission(apps)
    if perm is None:
        return

    for group in Group.objects.filter(Q(name__endswith="_MLDataManager")):
        project_pk = _project_pk_from_group(group)
        if project_pk is None:
            continue
        # Global add for parity with create_roles_for_project; the object-level
        # row below is what get_perms()/has_perm(perm, project) actually read.
        group.permissions.add(perm)
        GroupObjectPermission.objects.get_or_create(
            permission=perm,
            content_type=project_ct,
            object_pk=str(project_pk),
            group=group,
        )


def revoke_sync_from_mldatamanager(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    GroupObjectPermission = apps.get_model("guardian", "GroupObjectPermission")

    perm, project_ct = _sync_permission(apps)
    if perm is None:
        return

    # Only touch MLDataManager groups; ProjectManager holds sync_deployment
    # independently and must keep it.
    for group in Group.objects.filter(Q(name__endswith="_MLDataManager")):
        project_pk = _project_pk_from_group(group)
        if project_pk is None:
            continue
        group.permissions.remove(perm)
        GroupObjectPermission.objects.filter(
            permission=perm,
            content_type=project_ct,
            object_pk=str(project_pk),
            group=group,
        ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0094_enable_async_pipeline_workers"),
        ("guardian", "0002_generic_permissions_index"),
    ]

    operations = [
        migrations.RunPython(
            grant_sync_to_mldatamanager,
            revoke_sync_from_mldatamanager,
        ),
    ]
