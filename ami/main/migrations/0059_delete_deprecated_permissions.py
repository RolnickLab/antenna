from django.db import migrations


def delete_deprecated_permissions(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    deprecated_codenames = [
        "process_sourceimage",
        "process_single_image_job",
        "process_single_image_ml_job",
        "run_job",
        "retry_job",
        "cancel_job",
    ]

    permissions = Permission.objects.filter(codename__in=deprecated_codenames)
    for perm in permissions:
        print(f"Deleting permission: {perm.codename}")
        perm.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0058_alter_project_options_squashed_0067_alter_project_options"),
    ]

    operations = [
        migrations.RunPython(delete_deprecated_permissions, reverse_code=migrations.RunPython.noop),
    ]
