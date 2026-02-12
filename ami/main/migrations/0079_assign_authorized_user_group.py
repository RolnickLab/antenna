from django.db import migrations
import logging

logger = logging.getLogger(__name__)


def forwards(apps, schema_editor):
    logger.info("Starting migration: Assigning 'AuthorizedUser' role to all users...")

    User = apps.get_model("users", "User")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    try:
        project_ct = ContentType.objects.get(app_label="main", model="project")
        logger.info("Fetched ContentType for Project model.")
    except ContentType.DoesNotExist:
        logger.error("ContentType for Project model not found. Migration aborted.")
        return

    perm, created = Permission.objects.get_or_create(
        codename="create_project",
        content_type=project_ct,
        defaults={"name": "Can create a project"},
    )
    if created:
        logger.info("Created new permission: 'create_project'.")
    else:
        logger.info("Permission 'create_project' already exists.")

    group, group_created = Group.objects.get_or_create(name="AuthorizedUser")
    if group_created:
        logger.info("Created new group: 'AuthorizedUser'.")
    else:
        logger.info("Group 'AuthorizedUser' already exists.")

    group.permissions.add(perm)
    logger.info("Added 'create_project' permission to 'AuthorizedUser' group.")

    total_users = User.objects.count()
    logger.info(f"Assigning 'AuthorizedUser' group to {total_users} users...")

    for idx, user in enumerate(User.objects.all().iterator(), start=1):
        user.groups.add(group)
        if idx % 100 == 0:
            logger.info(f"Processed {idx}/{total_users} users...")

    logger.info("Successfully assigned 'AuthorizedUser' role to all users.")


def backwards(apps, schema_editor):
    logger.info("Reversing migration: Removing 'AuthorizedUser' role from users...")

    User = apps.get_model("users", "User")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    try:
        project_ct = ContentType.objects.get(app_label="main", model="project")
        logger.info("Fetched ContentType for Project model.")
    except ContentType.DoesNotExist:
        logger.warning("ContentType for Project model not found. Nothing to reverse.")
        return

    try:
        group = Group.objects.get(name="AuthorizedUser")
        logger.info("Fetched 'AuthorizedUser' group.")
    except Group.DoesNotExist:
        logger.warning("Group 'AuthorizedUser' not found. Nothing to reverse.")
        return

    total_users = User.objects.count()
    logger.info(f"Removing 'AuthorizedUser' group from {total_users} users...")

    for idx, user in enumerate(User.objects.all().iterator(), start=1):
        user.groups.remove(group)
        if idx % 100 == 0:
            logger.info(f"Processed {idx}/{total_users} users...")

    logger.info("Successfully removed 'AuthorizedUser' role from all users.")


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0078_classification_applied_to"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
