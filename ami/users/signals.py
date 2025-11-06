import logging

from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from ami.main.models import Project
from ami.users.models import User
from ami.users.roles import AuthorizedUser, GlobalRole, Role, create_roles_for_project

logger = logging.getLogger(__name__)


def create_project_based_roles(sender, **kwargs):
    """Creates predefined project based roles with specific permissions ."""

    logger.info("Creating roles for all projects")
    try:
        for project in Project.objects.all():
            try:
                create_roles_for_project(project)
            except Exception as e:
                logger.warning(f"Failed to create roles for project {project.pk} ({project.name}): {e}")
                continue
    except Exception as e:
        logger.warning(
            f"Failed to create roles during migration: {e}. This can be run manually via management command."
        )


def create_global_roles(sender, **kwargs):
    """
    Create or update all global role groups and synchronize their permissions.

    This function iterates through every subclass of `GlobalRole` (e.g. AuthorizedUser),
    ensures each role group exists, and syncs its assigned permissions according to
    the `model_level_permissions` list defined on the role class.
    """
    logger.info("Ensuring all global role groups and permissions are up to date")

    for role_cls in GlobalRole.__subclasses__():
        try:
            group, created = Group.objects.get_or_create(name=role_cls.get_group_name())
            role_cls.sync_group_permissions()
            logger.info(f"Synchronized global role: {role_cls.__name__} ({group.name})")
        except Exception as e:
            logger.warning(f"Failed to sync global role {role_cls.__name__}: {e}")


@receiver(m2m_changed, sender=Group.user_set.through)
def manage_project_membership(sender, instance, action, reverse, model, pk_set, **kwargs):
    """
    When a user is added/removed from a permissions group, update project members accordingly.

    """
    if action not in ["post_add", "post_remove"]:
        return  # Only handle add and remove actions

    # Temporarily disconnect the signal before updating project.members to prevent infinite recursion.
    m2m_changed.disconnect(manage_project_membership, sender=Group.user_set.through)
    logger.debug("Disconnecting signal to prevent infinite recursion.")
    try:
        with transaction.atomic():  # Ensure DB consistency
            for group in Group.objects.filter(pk__in=pk_set):
                # @TODO : Refactor after adding the project <-> Group formal relationship
                parts = group.name.split("_")  # Expected format: {project_id}_{project_name}_{Role}

                try:
                    project_id = int(parts[0])
                    project = Project.objects.get(id=project_id)
                except (ValueError, Project.DoesNotExist):
                    logger.warning(f"Skipping invalid group or missing project: {group.name}")
                    continue

                user = instance
                if action == "post_add":
                    # Add user to project members if not already in
                    if not project.members.filter(id=user.id).exists():
                        project.members.add(user)
                        logger.info(f"Added {user.email} to project {project.name} members.")

                elif action == "post_remove":
                    # Check if user still has any role in this project and they exist in the project members
                    has_any_role = Role.user_has_any_role(user, project)
                    if not has_any_role and project.members.filter(id=user.id).exists():
                        project.members.remove(user)
                        logger.info(f"Removed {user.email} from project {project.name} members (no remaining roles).")

    finally:
        # Reconnect the signal after updating members
        m2m_changed.connect(manage_project_membership, sender=Group.user_set.through)
        logger.debug("Reconnecting signal after updating project members.")


@receiver(post_save, sender=User)
def assign_authorized_user_group(sender, instance, created, **kwargs):
    if created:
        logger.info(f"Assigning AuthorizedUser role to new user {instance.email}")
        AuthorizedUser.assign_user(instance)
