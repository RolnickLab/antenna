import logging
from contextlib import contextmanager
from contextvars import ContextVar

from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from ami.main.models import Project, UserProjectMembership
from ami.users.roles import Role, create_roles_for_project

logger = logging.getLogger(__name__)

# Thread-safe flag to suppress the manage_project_membership signal handler.
# When True, the handler returns early without creating/deleting memberships.
# This avoids the need to globally disconnect/reconnect the signal, which is
# racy under concurrent requests (another request's group changes would be
# silently ignored while the signal is disconnected).
_skip_membership_signal: ContextVar[bool] = ContextVar("_skip_membership_signal", default=False)


@contextmanager
def suppress_membership_signal():
    """Suppress manage_project_membership for the current thread/coroutine.

    Use this when managing memberships and roles directly (e.g., in API views)
    so the signal doesn't interfere by creating/deleting memberships in response
    to the group changes you're making intentionally.
    """
    token = _skip_membership_signal.set(True)
    try:
        yield
    finally:
        _skip_membership_signal.reset(token)


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
        return

    if _skip_membership_signal.get():
        logger.debug("Skipping manage_project_membership (suppressed by caller).")
        return

    # Suppress the signal for the duration of this handler to prevent recursion:
    # modifying project.members triggers set_project_members_permissions, which calls
    # BasicMember.assign_user, which modifies Group.user_set, which would re-enter here.
    with suppress_membership_signal():
        with transaction.atomic():
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
                    _, created = UserProjectMembership.objects.get_or_create(project=project, user=user)
                    if created:
                        logger.info(f"Added {user.email} to project {project.name} members.")
                    else:
                        logger.info(f"User {user.email} already a member of project {project.name}.")

                elif action == "post_remove":
                    has_any_role = Role.user_has_any_role(user, project)
                    if not has_any_role:
                        UserProjectMembership.objects.filter(project=project, user=user).delete()
                        logger.info(f"Removed {user.email} from project {project.name} members")
