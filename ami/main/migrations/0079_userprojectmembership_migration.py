from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion


def forwards(apps, schema_editor):
    Project = apps.get_model("main", "Project")
    User = apps.get_model(settings.AUTH_USER_MODEL.split(".")[0], settings.AUTH_USER_MODEL.split(".")[1])
    UserProjectMembership = apps.get_model("main", "UserProjectMembership")

    # Copy data from old implicit M2M
    # The auto-created table is named main_project_members
    through_table = "main_project_members"

    # Use schema_editor to read rows (ORM cannot query auto-M2M)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"SELECT project_id, user_id FROM {through_table};")
        rows = cursor.fetchall()

    # Create new through model entries using ORM
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
        ("main", "0078_classification_applied_to"),
    ]

    operations = [
        # 1. Create through model
        migrations.CreateModel(
            name="UserProjectMembership",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
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
            "DROP TABLE IF EXISTS main_project_members;", reverse_sql="DROP TABLE IF EXISTS main_project_members;"
        ),
        # 4. ONLY update Django's internal model state (NO DB change)
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
    ]
