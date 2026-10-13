"""
Add two custom permissions to ``Project`` and grant them to the relevant role
groups:

* ``regroup_sessions_deployment`` — gates the
  ``POST /api/v2/deployments/<pk>/regroup-sessions/`` action via
  ``BaseModel.check_custom_permission`` (codename = ``{action}_{model_name}``).
  Mirrors how ``sync_deployment`` is granted. Goes to ``ProjectManager``.

* ``run_regroup_events_job`` — gates create/run/cancel of the new
  ``RegroupEventsJob`` type via ``Job.check_custom_permission`` (codename =
  ``run_{job_type_key}_job``). Mirrors how ``run_data_storage_sync_job`` is
  granted. Goes to ``MLDataManager`` (which ``ProjectManager`` inherits from).
"""

from django.db import migrations
from django.db.models import Q


def _get_or_create_perm(apps, codename: str, name: str):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    project_ct = ContentType.objects.get(app_label="main", model="project")
    perm, _ = Permission.objects.get_or_create(
        codename=codename,
        content_type=project_ct,
        defaults={"name": name},
    )
    return perm, project_ct


def grant_new_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    ContentType = apps.get_model("contenttypes", "ContentType")

    try:
        ContentType.objects.get(app_label="main", model="project")
    except ContentType.DoesNotExist:
        return

    regroup_perm, _ = _get_or_create_perm(
        apps,
        "regroup_sessions_deployment",
        "Can regroup deployment captures into sessions",
    )
    run_regroup_job_perm, _ = _get_or_create_perm(
        apps,
        "run_regroup_events_job",
        "Can run/retry/cancel Regroup Events jobs",
    )

    project_manager_groups = Group.objects.filter(Q(name__endswith="_ProjectManager"))
    for group in project_manager_groups:
        group.permissions.add(regroup_perm)

    # run_regroup_events_job goes to anyone who can run a sync job today —
    # MLDataManager is the primary holder; ProjectManager inherits from it
    # and has its own role group.
    job_runner_groups = Group.objects.filter(Q(name__endswith="_MLDataManager") | Q(name__endswith="_ProjectManager"))
    for group in job_runner_groups:
        group.permissions.add(run_regroup_job_perm)


def revoke_new_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    GroupObjectPermission = apps.get_model("guardian", "GroupObjectPermission")

    try:
        project_ct = ContentType.objects.get(app_label="main", model="project")
    except ContentType.DoesNotExist:
        return

    for codename in ("regroup_sessions_deployment", "run_regroup_events_job"):
        try:
            perm = Permission.objects.get(codename=codename, content_type=project_ct)
        except Permission.DoesNotExist:
            continue
        role_groups = Group.objects.filter(Q(name__endswith="_ProjectManager") | Q(name__endswith="_MLDataManager"))
        for group in role_groups:
            group.permissions.remove(perm)
        GroupObjectPermission.objects.filter(
            permission=perm,
            content_type=project_ct,
            group__in=role_groups,
        ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0088_detection_det_srcimg_created_idx"),
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
                    ("run_regroup_events_job", "Can run/retry/cancel Regroup Events jobs"),
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
            grant_new_permissions,
            revoke_new_permissions,
        ),
    ]
