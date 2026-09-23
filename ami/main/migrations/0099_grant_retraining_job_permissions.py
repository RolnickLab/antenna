"""
Grant the new retraining job permissions to existing projects' role groups.

``Job.check_custom_permission`` builds its codename from the job type key, so
``train_classifier``, ``evaluate_algorithm`` and ``generate_embeddings`` each need a
``run_<key>_job`` permission or ``has_perm`` matches nothing and only superusers can run
them. The permissions are declared in ``0098``; this grants them.

Both roles are backfilled, unlike ``0095``: that migration closed a gap where
``ProjectManager`` already held the permission, whereas these three are new to everyone.
``ProjectManager`` inherits ``MLDataManager``'s permission set, but the guardian rows are
per group, so each needs its own.

Permissions here are guardian **object-level** grants on each project, which is what
``has_perm("run_train_classifier_job", project)`` reads. Adding only to
``group.permissions`` would not appear in ``get_perms`` and the jobs would stay
unrunnable.

New projects pick this up through ``create_roles_for_project``. The ``post_migrate``
signal re-syncs every project's role permissions anyway, so this is belt-and-suspenders;
it is kept so the grant is explicit rather than a side effect.
"""

from django.db import migrations
from django.db.models import Q

CODENAMES = (
    "run_generate_embeddings_job",
    "run_train_classifier_job",
    "run_evaluate_algorithm_job",
)

# ProjectManager inherits MLDataManager's permissions, but guardian rows are per group.
ROLE_GROUP_SUFFIXES = ("_MLDataManager", "_ProjectManager")


def _permissions(apps):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    try:
        project_ct = ContentType.objects.get(app_label="main", model="project")
    except ContentType.DoesNotExist:
        return [], None
    perms = list(Permission.objects.filter(codename__in=CODENAMES, content_type=project_ct))
    return perms, project_ct


def _project_pk_from_group(group):
    # Group names are "{project_pk}_{project_name}_{RoleName}"; the pk is the immutable
    # leading segment (the name itself can contain underscores).
    try:
        return int(group.name.split("_", 1)[0])
    except (ValueError, IndexError):
        return None


def _role_groups(Group):
    query = Q()
    for suffix in ROLE_GROUP_SUFFIXES:
        query |= Q(name__endswith=suffix)
    return Group.objects.filter(query)


def grant(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    GroupObjectPermission = apps.get_model("guardian", "GroupObjectPermission")

    perms, project_ct = _permissions(apps)
    if not perms:
        return

    for group in _role_groups(Group):
        project_pk = _project_pk_from_group(group)
        if project_pk is None:
            continue
        for perm in perms:
            # Global add for parity with create_roles_for_project; the object-level row
            # below is what has_perm(perm, project) actually reads.
            group.permissions.add(perm)
            GroupObjectPermission.objects.get_or_create(
                permission=perm,
                content_type=project_ct,
                object_pk=str(project_pk),
                group=group,
            )


def revoke(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    GroupObjectPermission = apps.get_model("guardian", "GroupObjectPermission")

    perms, project_ct = _permissions(apps)
    if not perms:
        return

    for group in _role_groups(Group):
        project_pk = _project_pk_from_group(group)
        if project_pk is None:
            continue
        for perm in perms:
            group.permissions.remove(perm)
            GroupObjectPermission.objects.filter(
                permission=perm,
                content_type=project_ct,
                object_pk=str(project_pk),
                group=group,
            ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0098_job_permissions_for_retraining"),
        ("guardian", "0002_generic_permissions_index"),
    ]

    operations = [
        migrations.RunPython(grant, revoke),
    ]
