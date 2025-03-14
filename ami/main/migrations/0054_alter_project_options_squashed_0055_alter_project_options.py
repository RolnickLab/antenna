# Generated by Django 4.2.10 on 2025-02-10 17:01

from django.db import migrations


class Migration(migrations.Migration):
    replaces = [("main", "0054_alter_project_options"), ("main", "0055_alter_project_options")]

    dependencies = [
        ("main", "0053_alter_classification_algorithm"),
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
                    ("run_job", "Can run a job"),
                    ("delete_job", "Can delete a job"),
                    ("retry_job", "Can retry a job"),
                    ("cancel_job", "Can cancel a job"),
                    ("create_deployment", "Can create a deployment"),
                    ("delete_deployment", "Can delete a deployment"),
                    ("update_deployment", "Can update a deployment"),
                    ("create_sourceimagecollection", "Can create a collection"),
                    ("update_sourceimagecollection", "Can update a collection"),
                    ("delete_sourceimagecollection", "Can delete a collection"),
                    ("populate_sourceimagecollection", "Can populate a collection"),
                    ("star_sourceimage", "Can star a source image"),
                    ("create_s3storagesource", "Can create storage"),
                    ("delete_s3storagesource", "Can delete storage"),
                    ("update_s3storagesource", "Can update storage"),
                    ("create_site", "Can create a site"),
                    ("delete_site", "Can delete a site"),
                    ("update_site", "Can update a site"),
                    ("create_device", "Can create a device"),
                    ("delete_device", "Can delete a device"),
                    ("update_device", "Can update a device"),
                    ("view_private_data", "Can view private data"),
                    ("trigger_exports", "Can trigger data exports"),
                ],
            },
        ),
    ]
