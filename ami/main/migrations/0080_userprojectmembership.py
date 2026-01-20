from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion


def forwards(apps, schema_editor):
    UserProjectMembership = apps.get_model("main", "UserProjectMembership")

    # Copy data from old implicit M2M table
    through_table = "main_project_members"

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"SELECT project_id, user_id FROM {through_table};")
        rows = cursor.fetchall()

    # Create new through model entries
    for project_id, user_id in rows:
        UserProjectMembership.objects.get_or_create(
            project_id=project_id,
            user_id=user_id,
        )


def backwards(apps, schema_editor):
    UserProjectMembership = apps.get_model("main", "UserProjectMembership")

    with schema_editor.connection.cursor() as cursor:
        # Recreate old table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS main_project_members (
                id serial PRIMARY KEY,
                project_id integer NOT NULL,
                user_id integer NOT NULL
            );
        """
        )
        # Copy back membership data
        for m in UserProjectMembership.objects.all():
            cursor.execute(
                "INSERT INTO main_project_members (project_id, user_id) VALUES (%s, %s)",
                [m.project_id, m.user_id],
            )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("main", "0079_alter_project_options"),
    ]

    operations = [
        # 1. Create through model
        migrations.CreateModel(
            name="UserProjectMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="project_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="project_memberships",
                        to="main.project",
                    ),
                ),
            ],
            options={"unique_together": {("user", "project")}},
        ),
        # 2. Copy old M2M data to new through model
        migrations.RunPython(forwards, backwards),
        # 3. Drop old M2M implicit table
        migrations.RunSQL(
            "DROP TABLE IF EXISTS main_project_members;",
            reverse_sql="DROP TABLE IF EXISTS main_project_members;",
        ),
        # 4. Update Django's internal model state (NO DB change)
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="project",
                    name="members",
                    field=models.ManyToManyField(
                        blank=True,
                        related_name="user_projects",
                        through="main.UserProjectMembership",
                        to=settings.AUTH_USER_MODEL,
                    ),
                )
            ],
        ),
        # 5. Update Project permissions to current state
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
                    (
                        "update_userprojectmembership",
                        "Can update a user's project membership and role in the project",
                    ),
                    ("delete_userprojectmembership", "Can remove a user from the project"),
                    ("create_dataexport", "Can create a data export"),
                    ("update_dataexport", "Can update a data export"),
                    ("delete_dataexport", "Can delete a data export"),
                    ("view_private_data", "Can view private data"),
                ],
            },
        ),
    ]
