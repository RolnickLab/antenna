"""
Grant the existing ``sync_deployment`` permission to ``MLDataManager`` role
groups on projects that already exist.

``MLDataManager`` already holds ``run_data_storage_sync_job`` (it can run/retry a
sync job) but not ``sync_deployment`` (which gates *starting* a sync from a
station via ``POST /api/v2/deployments/<pk>/sync/`` and the bulk
``.../sync-all/`` action). This closes that gap so ML data managers can trigger
syncs, not only manage the resulting jobs. ``ProjectManager`` already has the
permission and is unaffected.

New projects pick this up automatically through ``create_roles_for_project``
(``MLDataManager`` now includes the permission); this migration backfills the
role groups of existing projects. The ``sync_deployment`` permission itself is
already defined on ``Project.Meta.permissions``, so there is no model/schema
change here — only a data backfill.
"""

from django.db import migrations
from django.db.models import Q


def grant_sync_to_mldatamanager(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    try:
        project_ct = ContentType.objects.get(app_label="main", model="project")
    except ContentType.DoesNotExist:
        return

    try:
        perm = Permission.objects.get(codename="sync_deployment", content_type=project_ct)
    except Permission.DoesNotExist:
        return

    for group in Group.objects.filter(Q(name__endswith="_MLDataManager")):
        group.permissions.add(perm)


def revoke_sync_from_mldatamanager(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    GroupObjectPermission = apps.get_model("guardian", "GroupObjectPermission")

    try:
        project_ct = ContentType.objects.get(app_label="main", model="project")
    except ContentType.DoesNotExist:
        return

    try:
        perm = Permission.objects.get(codename="sync_deployment", content_type=project_ct)
    except Permission.DoesNotExist:
        return

    # Only touch MLDataManager groups; ProjectManager holds sync_deployment
    # independently and must keep it.
    mldm_groups = Group.objects.filter(Q(name__endswith="_MLDataManager"))
    for group in mldm_groups:
        group.permissions.remove(perm)
    GroupObjectPermission.objects.filter(
        permission=perm,
        content_type=project_ct,
        group__in=mldm_groups,
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
