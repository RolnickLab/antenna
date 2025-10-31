import logging

from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from ami.main.models import Project
from ami.users.models import User
from ami.users.roles import AuthorizedUser, Role, create_roles_for_project

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
    Synchronize a Project's members when a User is added to or removed from a permission Group.
    
    Handles m2m_changed signals from Group.user_set.through and processes only the "post_add" and "post_remove" actions. For each affected Group, the handler extracts a project ID from the group's name (expected format "{project_id}_{project_name}_{Role}"), resolves the corresponding Project, and then:
    - on "post_add": adds the user to project.members if not already present;
    - on "post_remove": removes the user from project.members only if the user has no remaining roles in that project.
    
    Updates are performed inside a transaction, the handler temporarily disconnects itself to avoid recursive signal calls, and Groups with invalid names or missing Projects are skipped.
    
    Parameters:
        sender: The signal sender (ignored by this handler).
        instance: The User instance being added/removed.
        action (str): The m2m_changed action; only "post_add" and "post_remove" are handled.
        reverse: Boolean indicating signal direction (ignored by this handler).
        model: The through-model class (ignored by this handler).
        pk_set (set[int]): Set of primary keys of Groups affected by the change.
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
def assign_authenticated_users_group(sender, instance, created, **kwargs):
    """
    Assigns the AuthorizedUser role to newly created User instances.
    
    When a User is created (created is True), logs the assignment and calls AuthorizedUser.assign_user(instance).
    
    Parameters:
        sender (type): The model class that sent the signal.
        instance (ami.users.models.User): The User instance that was saved.
        created (bool): `True` if the instance was created, `False` if updated.
        **kwargs: Additional signal keyword arguments.
    """
    if created:
        logger.info(f"Assigning AuthorizedUser role to new user {instance.email}")
        AuthorizedUser.assign_user(instance)