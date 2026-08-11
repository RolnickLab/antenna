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
#
# Why not just disconnect/reconnect the signal?
# Django signals are global (process-wide). Disconnecting in a request handler
# suppresses the signal for ALL concurrent requests in the same process, not
# just the current one. Under concurrent load (gunicorn threads, async workers),
# another request's group changes would silently skip the handler, leaving
# users in permission groups without corresponding UserProjectMembership records.
# ContextVar is scoped to the current thread/coroutine, so suppression only
# affects the caller that requested it.
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
    """
    Creates predefined roles with specific permissions.
    Only runs when role schema version has changed.
    """
    from ami.users.models import RoleSchemaVersion

    # Quick check - does schema need updating?
    if not RoleSchemaVersion.needs_update():
        logger.debug("Role schema is up to date, skipping role creation")
        return

    logger.info("Role schema version changed - updating roles for all projects")
    project_count = Project.objects.count()

    if project_count > 100:
        logger.warning(
            f"Updating roles for {project_count} projects. "
            f"This may take a while. Consider running 'python manage.py update_roles' "
            f"separately for better control."
        )

    try:
        for project in Project.objects.all():
            try:
                create_roles_for_project(project, force_update=True)
            except Exception as e:
                logger.warning(f"Failed to create roles for project {project.pk} ({project.name}): {e}")
                continue

        # Mark schema as updated
        RoleSchemaVersion.mark_updated(description="Post-migration role update")
        logger.info(f"Successfully updated roles for {project_count} projects")

    except Exception as e:
        logger.error(f"Failed to create roles during migration: {e}")


@receiver(m2m_changed, sender=Group.user_set.through)
def manage_project_membership(sender, instance, action, reverse, model, pk_set, **kwargs):
    """
    When a user is added/removed from a permissions group, update project members accordingly.
    """
    if action not in ["post_add", "post_remove"]:
        return

    # This handler expects instance=User, pk_set=Group PKs, which is the case
    # when reverse=False (called via user.groups.add/remove()). All callers go through
    # Role.assign_user and Role.unassign_user. When reverse=True (group.user_set.add/remove()),
    # instance is a Group and pk_set contains User PKs, which would break lookups below.
    if reverse:
        return

    if _skip_membership_signal.get():
        logger.debug("Skipping manage_project_membership (suppressed by caller).")
        return

    # Suppress re-entrancy: Role.assign_user (called elsewhere, e.g. from
    # set_project_members_permissions in main/signals.py) modifies Group.user_set,
    # which would fire this handler again. The suppression is scoped to this
    # thread only via ContextVar — other concurrent requests are unaffected.
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
