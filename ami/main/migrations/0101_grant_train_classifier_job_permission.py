"""
Grant ``run_train_classifier_job`` to the role that already runs the other ML jobs.

``create_roles_for_project`` gives new projects their role permissions, and a
``post_migrate`` signal re-syncs every project on migrate, so this backfill is belt and
braces. It is kept so the grant is explicit rather than a side effect of a signal.

Guardian reads object-level rows, so each project gets a ``GroupObjectPermission``; adding
to ``group.permissions`` alone would not appear in ``get_perms(user, project)``. Mirrors
``0099_grant_occurrence_set_permissions``.
"""

from django.db import migrations
from django.db.models import Q

PERMISSION = "run_train_classifier_job"
ROLE_GROUP_SUFFIXES = ("_MLDataManager", "_ProjectManager")


def _permission(apps):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    try:
        project_ct = ContentType.objects.get(app_label="main", model="project")
    except ContentType.DoesNotExist:
        return None, None
    try:
        return Permission.objects.get(codename=PERMISSION, content_type=project_ct), project_ct
    except Permission.DoesNotExist:
        return None, None


def _project_pk_from_group(group):
    # Group names are "{project_pk}_{project_name}_{RoleName}"; the pk is the immutable
    # leading segment, since a project name may itself contain underscores.
    try:
        return int(group.name.split("_", 1)[0])
    except (ValueError, IndexError):
        return None


def _role_groups(apps):
    Group = apps.get_model("auth", "Group")
    query = Q()
    for suffix in ROLE_GROUP_SUFFIXES:
        query |= Q(name__endswith=suffix)
    return Group.objects.filter(query)


def grant(apps, schema_editor):
    GroupObjectPermission = apps.get_model("guardian", "GroupObjectPermission")
    permission, project_ct = _permission(apps)
    if permission is None:
        return

    for group in _role_groups(apps):
        project_pk = _project_pk_from_group(group)
        if project_pk is None:
            continue
        group.permissions.add(permission)
        GroupObjectPermission.objects.get_or_create(
            permission=permission,
            content_type=project_ct,
            object_pk=str(project_pk),
            group=group,
        )


def revoke(apps, schema_editor):
    GroupObjectPermission = apps.get_model("guardian", "GroupObjectPermission")
    permission, project_ct = _permission(apps)
    if permission is None:
        return

    for group in _role_groups(apps):
        project_pk = _project_pk_from_group(group)
        if project_pk is None:
            continue
        group.permissions.remove(permission)
        GroupObjectPermission.objects.filter(
            permission=permission,
            content_type=project_ct,
            object_pk=str(project_pk),
            group=group,
        ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0100_train_classifier_job_permission"),
        ("guardian", "0002_generic_permissions_index"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
