"""
Grant the occurrence set permissions to the ML data manager and project manager
roles of projects that already exist.

These roles curate capture sets, so they also curate occurrence sets. New projects
get the permissions from ``create_roles_for_project``. The grants are guardian
object-level rows on each project, which ``user.has_perm(perm, project)`` reads, as
in migration 0095.
"""

from django.db import migrations
from django.db.models import Q

PERMISSIONS = {
    "create_occurrenceset": "Can create an occurrence set",
    "update_occurrenceset": "Can update, freeze, and add or remove the occurrences of an occurrence set",
    "delete_occurrenceset": "Can delete an occurrence set",
}
ROLE_GROUPS = Q(name__endswith="_MLDataManager") | Q(name__endswith="_ProjectManager")


def _project_pk_from_group(group):
    # Group names are "{project_pk}_{project_name}_{RoleName}".
    try:
        return int(group.name.split("_", 1)[0])
    except (ValueError, IndexError):
        return None


def grant_occurrence_set_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    GroupObjectPermission = apps.get_model("guardian", "GroupObjectPermission")

    try:
        project_ct = ContentType.objects.get(app_label="main", model="project")
    except ContentType.DoesNotExist:
        # A new database has no projects and no role groups to grant to.
        return
    # Django creates Meta permissions after all migrations run, so create them here.
    permissions = [
        Permission.objects.get_or_create(codename=codename, content_type=project_ct, defaults={"name": name})[0]
        for codename, name in PERMISSIONS.items()
    ]
    grants = []
    for group in Group.objects.filter(ROLE_GROUPS):
        project_pk = _project_pk_from_group(group)
        if project_pk is None:
            continue
        group.permissions.add(*permissions)
        grants += [
            GroupObjectPermission(permission=permission, content_type=project_ct, object_pk=str(project_pk), group=group)
            for permission in permissions
        ]
    GroupObjectPermission.objects.bulk_create(grants, ignore_conflicts=True)


def revoke_occurrence_set_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    GroupObjectPermission = apps.get_model("guardian", "GroupObjectPermission")

    permissions = Permission.objects.filter(
        codename__in=PERMISSIONS, content_type__app_label="main", content_type__model="project"
    )
    for group in Group.objects.filter(ROLE_GROUPS):
        group.permissions.remove(*permissions)
    GroupObjectPermission.objects.filter(permission__in=permissions).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0100_occurrence_set"),
        ("guardian", "0002_generic_permissions_index"),
    ]

    operations = [
        migrations.RunPython(grant_occurrence_set_permissions, revoke_occurrence_set_permissions),
    ]
