"""
Add the ``regroup_sessions_deployment`` custom permission to ``Project`` and
grant it to existing ``ProjectManager`` role groups.

The new ``POST /api/v2/deployments/<pk>/regroup-sessions/`` action runs through
``BaseModel.check_custom_permission``, which builds the codename as
``{action}_{model_name}`` — for the ``regroup_sessions`` action on a
``Deployment`` viewset that resolves project permission via the parent project,
the perm needed is ``regroup_sessions_deployment``. Mirrors how
``sync_deployment`` is granted in ``ami.users.roles.ProjectManager``.
"""

from django.db import migrations
from django.db.models import Q


def grant_regroup_sessions_to_project_managers(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    try:
        project_ct = ContentType.objects.get(app_label="main", model="project")
    except ContentType.DoesNotExist:
        return

    perm, _ = Permission.objects.get_or_create(
        codename="regroup_sessions_deployment",
        content_type=project_ct,
        defaults={"name": "Can regroup deployment captures into sessions"},
    )

    role_groups = Group.objects.filter(Q(name__endswith="_ProjectManager"))
    for group in role_groups:
        group.permissions.add(perm)


def revoke_regroup_sessions_from_project_managers(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    GroupObjectPermission = apps.get_model("guardian", "GroupObjectPermission")

    try:
        project_ct = ContentType.objects.get(app_label="main", model="project")
    except ContentType.DoesNotExist:
        return
    try:
        perm = Permission.objects.get(codename="regroup_sessions_deployment", content_type=project_ct)
    except Permission.DoesNotExist:
        return

    role_groups = Group.objects.filter(Q(name__endswith="_ProjectManager"))
    for group in role_groups:
        group.permissions.remove(perm)

    GroupObjectPermission.objects.filter(
        permission=perm,
        content_type=project_ct,
        group__in=role_groups,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0084_revoke_delete_job_from_roles"),
        ("guardian", "0002_generic_permissions_index"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="project",
            options={
                "ordering": ["-priority", "created_at"],
                "permissions": [
                    ("create_identification", "Can create identifications"),
                    ("update_identification", "Can update identifications"),
                    ("delete_identification", "Can delete identifications"),
                    ("create_job", "Can create a job"),
                    ("update_job", "Can update a job"),
                    ("run_ml_job", "Can run/retry/cancel ML jobs"),
                    ("run_populate_captures_collection_job", "Can run/retry/cancel Populate Collection jobs"),
                    ("run_data_storage_sync_job", "Can run/retry/cancel Data Storage Sync jobs"),
                    ("run_data_export_job", "Can run/retry/cancel Data Export jobs"),
                    ("run_single_image_ml_job", "Can process a single capture"),
                    ("run_post_processing_job", "Can run/retry/cancel Post-Processing jobs"),
                    ("delete_job", "Can delete a job"),
                    ("create_deployment", "Can create a deployment"),
                    ("delete_deployment", "Can delete a deployment"),
                    ("update_deployment", "Can update a deployment"),
                    ("sync_deployment", "Can sync images to a deployment"),
                    ("regroup_sessions_deployment", "Can regroup deployment captures into sessions"),
                    ("create_sourceimagecollection", "Can create a collection"),
                    ("update_sourceimagecollection", "Can update a collection"),
                    ("delete_sourceimagecollection", "Can delete a collection"),
                    ("populate_sourceimagecollection", "Can populate a collection"),
                    ("create_sourceimage", "Can create a source image"),
                    ("update_sourceimage", "Can update a source image"),
                    ("delete_sourceimage", "Can delete a source image"),
                    ("star_sourceimage", "Can star a source image"),
                    ("create_sourceimageupload", "Can create a source image upload"),
                    ("update_sourceimageupload", "Can update a source image upload"),
                    ("delete_sourceimageupload", "Can delete a source image upload"),
                    ("create_s3storagesource", "Can create storage"),
                    ("delete_s3storagesource", "Can delete storage"),
                    ("update_s3storagesource", "Can update storage"),
                    ("test_s3storagesource", "Can test storage connection"),
                    ("create_site", "Can create a site"),
                    ("delete_site", "Can delete a site"),
                    ("update_site", "Can update a site"),
                    ("create_device", "Can create a device"),
                    ("delete_device", "Can delete a device"),
                    ("update_device", "Can update a device"),
                    ("view_userprojectmembership", "Can view project members"),
                    ("create_userprojectmembership", "Can add a user to the project"),
                    ("update_userprojectmembership", "Can update a user's project membership and role in the project"),
                    ("delete_userprojectmembership", "Can remove a user from the project"),
                    ("create_dataexport", "Can create a data export"),
                    ("update_dataexport", "Can update a data export"),
                    ("delete_dataexport", "Can delete a data export"),
                    ("create_projectpipelineconfig", "Can register pipelines for the project"),
                    ("update_projectpipelineconfig", "Can update pipeline configurations"),
                    ("delete_projectpipelineconfig", "Can remove pipelines from the project"),
                    ("create_taxalist", "Can create a taxa list"),
                    ("update_taxalist", "Can update a taxa list"),
                    ("delete_taxalist", "Can delete a taxa list"),
                    ("view_private_data", "Can view private data"),
                ],
            },
        ),
        migrations.RunPython(
            grant_regroup_sessions_to_project_managers,
            revoke_regroup_sessions_from_project_managers,
        ),
    ]
