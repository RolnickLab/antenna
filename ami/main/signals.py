import logging

from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models.signals import m2m_changed, post_save, pre_delete, pre_save
from django.dispatch import receiver
from guardian.shortcuts import assign_perm

from ami.main.models import Deployment, Event, Project
from ami.users.roles import BasicMember, ProjectManager, create_roles_for_project

from .models import User

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Project)
def set_project_owner_permissions(sender, instance, created, **kwargs):
    if created:
        create_roles_for_project(instance)
    if created and instance.owner:
        # assign owner project manager role
        ProjectManager.assign_user(instance.owner, instance)

    else:
        # Check for an owner change
        old_owner = instance.__dict__.get("_old_owner")  # Retrieve the old owner set in the pre-save signal
        if old_owner and old_owner != instance.owner:
            # remove old owner project manager role
            ProjectManager.unassign_user(old_owner, instance)

            # assign new owner project manager role
            ProjectManager.assign_user(instance.owner, instance)


@receiver(post_save, sender=Project)
def set_others_permissions(sender, instance, created, **kwargs):
    if created and instance.owner:
        others_perms = [Project.Permissions.VIEW_PROJECT]
        # assign permissions for other users
        all_other_users = User.objects.exclude(id=instance.owner.id)
        for user in all_other_users:
            for perm in others_perms:
                assign_perm(perm, user, instance)


@receiver(m2m_changed, sender=Project.members.through)
def set_project_members_permissions(sender, instance, action, pk_set, **kwargs):
    """
    Triggered when the Project.members ManyToManyField is modified.
    Assigns read/write permissions to newly added members, and unassigns permissions when members are removed.
    """

    if action == "post_add":
        # Get users added to the members list
        users_added = instance.members.filter(pk__in=pk_set)

        # assign basic member role
        for user in users_added:
            BasicMember.assign_user(user, instance)
    if action == "post_remove":
        # Get users removed to the members list
        users_removed = instance.members.model.objects.filter(pk__in=pk_set)

        # remove basic member role
        for user in users_removed:
            BasicMember.unassign_user(user, instance)


# Pre-save signal to track the old owner
@receiver(pre_save, sender=Project)
def track_old_owner(sender, instance, **kwargs):
    """
    Track the previous owner before saving the project.
    This is used to detect owner changes in `set_project_owner_permissions`.
    """
    if instance.pk:  # Check if the object already exists in the database
        instance._old_owner = sender.objects.get(pk=instance.pk).owner
    else:
        instance._old_owner = None


@receiver(post_save, sender=Project)
def update_project_groups(sender, instance, **kwargs):
    """Update all project-related permission groups when the project is renamed."""

    prefix = f"{instance.pk}_"
    groups = Group.objects.filter(name__startswith=prefix)

    logger.info(f"Project name: {instance.name}")

    for group in groups:
        # Find the last underscore `_` to separate the project name and role
        last_underscore_index = group.name.rfind("_")

        if last_underscore_index != -1:
            role_name_start_index = last_underscore_index + 1
            role = group.name[role_name_start_index:]  # Extract role name after the last `_`
            # @TODO : Refactor after adding the project <-> Group formal relationship
            new_group_name = f"{prefix}{instance.name}_{role}"

            # Check if a group with the new name already exists
            if not Group.objects.filter(name=new_group_name).exists():
                logger.info(f"Changing permission group name from {group.name} to: {new_group_name}")
                group.name = new_group_name
                group.save()


@receiver(pre_delete, sender=Project)
def delete_project_groups(sender, instance, **kwargs):
    """Delete all project-related permission groups when the project is deleted."""
    prefix = f"{instance.pk}_"
    # Find and delete all groups that start with {project_id}_
    Group.objects.filter(name__startswith=prefix).delete()


# ============================================================================
# Project Default Filters Update Signals
# ============================================================================
# These signals handle efficient updates to calculated fields for project-related
# objects (such as Deployments and Events) whenever a project's default filter
# values change.
#
# Specifically, they trigger recalculation of cached counts when:
#   - The project's default score threshold is updated
#   - The project's default include taxa are modified
#   - The project's default exclude taxa are modified
#
# This ensures that cached counts (e.g., occurrences_count, taxa_count) remain
# accurate and consistent with the active filter configuration for each project.
# ============================================================================
def refresh_cached_counts_for_project(project: Project):
    """
    Refresh cached counts for Deployments and Events belonging to a project.
    """
    logger.info(f"Refreshing cached counts for project {project.pk}")

    with transaction.atomic():
        deployments = Deployment.objects.filter(project=project)
        for dep in deployments.iterator():
            dep.update_calculated_fields(save=True)

        events = Event.objects.filter(project=project)
        for ev in events.iterator():
            ev.update_calculated_fields(save=True)

    logger.info(
        f"Recomputed cached counts for {deployments.count()} deployments "
        f"and {events.count()} events in project {project.pk}."
    )


@receiver(pre_save, sender=Project)
def project_threshold_updated(sender, instance: Project, **kwargs):
    """Refresh cached counts when the project's default score threshold changes."""
    if not instance.pk:
        return  # skip new projects

    old = Project.objects.get(pk=instance.pk)
    if old.default_filters_score_threshold != instance.default_filters_score_threshold:
        logger.info(
            f"Default score threshold changed for project {instance.pk}: "
            f"{old.default_filters_score_threshold} => {instance.default_filters_score_threshold}"
        )
        refresh_cached_counts_for_project(instance)


@receiver(m2m_changed, sender=Project.default_filters_include_taxa.through)
def include_taxa_updated(sender, instance: Project, action, **kwargs):
    """Refresh cached counts when include taxa are modified."""
    if action in ["post_add", "post_remove", "post_clear"]:
        logger.info(f"Include taxa updated for project {instance.pk} (action={action})")
        refresh_cached_counts_for_project(instance)


@receiver(m2m_changed, sender=Project.default_filters_exclude_taxa.through)
def exclude_taxa_updated(sender, instance: Project, action, **kwargs):
    """Refresh cached counts when exclude taxa are modified."""
    if action in ["post_add", "post_remove", "post_clear"]:
        logger.info(f"Exclude taxa updated for project {instance.pk} (action={action})")
        refresh_cached_counts_for_project(instance)
