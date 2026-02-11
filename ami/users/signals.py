import logging

from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from ami.main.models import Project, UserProjectMembership
from ami.users.roles import Role, create_roles_for_project

logger = logging.getLogger(__name__)


def create_roles(sender, **kwargs):
    """Creates predefined roles with specific permissions ."""

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
                    # Use get_or_create on UserProjectMembership directly to avoid duplicates
                    # This ensures we don't create duplicates when roles are assigned
                    # outside of the API (e.g., admin page)
                    _, created = UserProjectMembership.objects.get_or_create(project=project, user=user)
                    if created:
                        logger.info(f"Added {user.email} to project {project.name} members.")
                    else:
                        logger.info(f"User {user.email} already a member of project {project.name}.")

                elif action == "post_remove":
                    # Check if user still has any role in this project
                    has_any_role = Role.user_has_any_role(user, project)
                    if not has_any_role:
                        # User has no roles left, remove membership using UserProjectMembership model
                        UserProjectMembership.objects.filter(project=project, user=user).delete()
                        logger.info(f"Removed {user.email} from project {project.name} members")

    finally:
        # Reconnect the signal after updating members
        m2m_changed.connect(manage_project_membership, sender=Group.user_set.through)
        logger.debug("Reconnecting signal after updating project members.")
