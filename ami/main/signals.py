import logging

from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver
from guardian.shortcuts import assign_perm, remove_perm

from .models import Project, User

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Project)
def set_project_owner_permissions(sender, instance, created, **kwargs):
    if created and instance.owner:
        # Assign permissions for the owner
        owner_perms = [Project.Permissions.VIEW, Project.Permissions.CHANGE, Project.Permissions.DELETE]
        for perm in owner_perms:
            assign_perm(perm, instance.owner, instance)

    else:
        # Check for an owner change
        old_owner = instance.__dict__.get("_old_owner")  # Retrieve the old owner set in the pre-save signal
        if old_owner and old_owner != instance.owner:
            # Remove permissions from the old owner
            old_owner_perms = [Project.Permissions.CHANGE, Project.Permissions.DELETE]
            for perm in old_owner_perms:
                remove_perm(perm, old_owner, instance)

            # Assign permissions to the new owner
            new_owner_perms = [Project.Permissions.CHANGE, Project.Permissions.DELETE]
            for perm in new_owner_perms:
                assign_perm(perm, instance.owner, instance)


@receiver(post_save, sender=Project)
def set_others_permissions(sender, instance, created, **kwargs):
    if created and instance.owner:
        others_perms = [Project.Permissions.VIEW]
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

        # Assign permissions to each new member
        for user in users_added:
            assign_perm(Project.Permissions.CHANGE, user, instance)
    if action == "post_remove":
        # Get users removed to the members list
        users_removed = instance.members.model.objects.filter(pk__in=pk_set)
        # Assign permissions to each new member
        for user in users_removed:
            remove_perm(Project.Permissions.CHANGE, user, instance)


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
