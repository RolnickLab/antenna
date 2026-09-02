"""
Strip the ``delete_job`` permission from existing per-project ``MLDataManager``
and ``ProjectManager`` role groups.

Job deletion is restricted to superusers (Job rows are kept in the DB for audit
and traceability), so non-superuser roles must not retain ``delete_job``. The
``delete_job`` codename itself remains a valid permission on ``Project`` — it
just shouldn't be granted to anyone via the role system.

The role groups follow the naming convention ``<project_pk>_<project_name>_<RoleClass>``
established by ``ami.users.roles.create_roles_for_project``. We rely on the
suffix to identify groups for the two roles that previously held the perm.

Reverse is a no-op: re-granting ``delete_job`` would re-introduce the
vulnerability this migration closes.
"""

from django.db import migrations
from django.db.models import Q


def remove_delete_job_from_role_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    GroupObjectPermission = apps.get_model("guardian", "GroupObjectPermission")

    try:
        project_ct = ContentType.objects.get(app_label="main", model="project")
    except ContentType.DoesNotExist:
        return

    try:
        delete_job_perm = Permission.objects.get(
            codename="delete_job",
            content_type=project_ct,
        )
    except Permission.DoesNotExist:
        return

    role_groups = Group.objects.filter(
        Q(name__endswith="_MLDataManager") | Q(name__endswith="_ProjectManager"),
    )

    for group in role_groups:
        group.permissions.remove(delete_job_perm)

    GroupObjectPermission.objects.filter(
        permission=delete_job_perm,
        content_type=project_ct,
        group__in=role_groups,
    ).delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0083_dedupe_taxalist_names"),
        ("guardian", "0002_generic_permissions_index"),
    ]

    operations = [
        migrations.RunPython(remove_delete_job_from_role_groups, noop_reverse),
    ]
