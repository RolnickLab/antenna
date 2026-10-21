"""
Give the occurrence set permissions to the roles that manage a project's ML data.

New projects get these permissions from ``create_roles_for_project``. This migration adds
them to existing projects. Guardian checks object-level rows (``GroupObjectPermission``),
so each project gets one row per role group, not only a group-level permission.
``ProjectManager`` inherits from ``MLDataManager``, so both groups get the rows.
"""

from django.db import migrations
from django.db.models import Q

PERMISSIONS = ("create_occurrenceset", "update_occurrenceset", "delete_occurrenceset")
ROLE_GROUP_SUFFIXES = ("_MLDataManager", "_ProjectManager")


def _permissions(apps):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    try:
        project_ct = ContentType.objects.get(app_label="main", model="project")
    except ContentType.DoesNotExist:
        return [], None
    found = list(Permission.objects.filter(codename__in=PERMISSIONS, content_type=project_ct))
    return found, project_ct


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
    permissions, project_ct = _permissions(apps)
    if not permissions:
        return

    for group in _role_groups(apps):
        project_pk = _project_pk_from_group(group)
        if project_pk is None:
            continue
        for permission in permissions:
            group.permissions.add(permission)
            GroupObjectPermission.objects.get_or_create(
                permission=permission,
                content_type=project_ct,
                object_pk=str(project_pk),
                group=group,
            )


def revoke(apps, schema_editor):
    GroupObjectPermission = apps.get_model("guardian", "GroupObjectPermission")
    permissions, project_ct = _permissions(apps)
    if not permissions:
        return

    for group in _role_groups(apps):
        project_pk = _project_pk_from_group(group)
        if project_pk is None:
            continue
        for permission in permissions:
            group.permissions.remove(permission)
            GroupObjectPermission.objects.filter(
                permission=permission,
                content_type=project_ct,
                object_pk=str(project_pk),
                group=group,
            ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0100_occurrence_set"),
        ("guardian", "0002_generic_permissions_index"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
