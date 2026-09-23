"""
Grant ``run_post_processing_job`` to ``MLDataManager`` and ``ProjectManager`` role groups on
existing projects, so the roles that run ML jobs can also start tracking runs through the jobs API.

The grant is a guardian object-level permission per project, which is what
``user.has_perm(codename, project)`` reads; see 0095 for the same pattern. The
``post_migrate`` role sync also applies it, and this migration keeps the grant explicit.
"""

from django.db import migrations
from django.db.models import Q

CODENAME = "run_post_processing_job"
# ProjectManager inherits MLDataManager's permissions, so both groups hold the grant.
ROLE_SUFFIXES = ("_MLDataManager", "_ProjectManager")


def _role_groups() -> Q:
    return Q(name__endswith=ROLE_SUFFIXES[0]) | Q(name__endswith=ROLE_SUFFIXES[1])


def _permission(apps):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    try:
        project_ct = ContentType.objects.get(app_label="main", model="project")
    except ContentType.DoesNotExist:
        return None, None
    try:
        return Permission.objects.get(codename=CODENAME, content_type=project_ct), project_ct
    except Permission.DoesNotExist:
        return None, None


def _project_pk_from_group(group):
    # Group names are "{project_pk}_{project_name}_{RoleName}"; the pk is the leading segment.
    try:
        return int(group.name.split("_", 1)[0])
    except (ValueError, IndexError):
        return None


def grant(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    GroupObjectPermission = apps.get_model("guardian", "GroupObjectPermission")

    perm, project_ct = _permission(apps)
    if perm is None:
        return
    for group in Group.objects.filter(_role_groups()):
        project_pk = _project_pk_from_group(group)
        if project_pk is None:
            continue
        group.permissions.add(perm)
        GroupObjectPermission.objects.get_or_create(
            permission=perm, content_type=project_ct, object_pk=str(project_pk), group=group
        )


def revoke(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    GroupObjectPermission = apps.get_model("guardian", "GroupObjectPermission")

    perm, project_ct = _permission(apps)
    if perm is None:
        return
    for group in Group.objects.filter(_role_groups()):
        project_pk = _project_pk_from_group(group)
        if project_pk is None:
            continue
        group.permissions.remove(perm)
        GroupObjectPermission.objects.filter(
            permission=perm, content_type=project_ct, object_pk=str(project_pk), group=group
        ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0100_occurrence_track_stats"),
        ("guardian", "0002_generic_permissions_index"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
