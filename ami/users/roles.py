import logging

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import assign_perm, get_perms, remove_perm

from ami.main.models import Project

logger = logging.getLogger(__name__)


class Role:
    """Base class for all roles."""

    permissions = {Project.Permissions.VIEW}

    # @TODO : Refactor after adding the project <-> Group formal relationship
    @classmethod
    def get_group_name(cls, project):
        """
        Construct the name of the group that manages a role for a given project.
        """
        return f"{project.pk}_{project.name}_{cls.__name__}"

    @classmethod
    def assign_user(cls, user, project):
        # Get or create the Group
        # @TODO Make the relationship between the group and the project more formal (use a many-to-many field)
        group_name = cls.get_group_name(project)
        group, created = Group.objects.get_or_create(name=group_name)
        if created:
            logger.info(f"Created permission group {group_name} for project {project}")
        # Add user to group
        user.groups.add(group)

    @classmethod
    def unassign_user(cls, user, project):
        group_name = cls.get_group_name(project)
        group = Group.objects.get(name=group_name)
        # remove user from group
        user.groups.remove(group)

    @classmethod
    def has_role(cls, user, project):
        """Checks if the user has the role permissions on the given project."""
        group_name = cls.get_group_name(project)
        return user.groups.filter(name=group_name).exists()

    @staticmethod
    def user_has_any_role(user, project):
        """Checks if the user has any role assigned to a given project."""
        return any(role_class.has_role(user, project) for role_class in Role.__subclasses__())


class BasicMember(Role):
    permissions = Role.permissions | {
        Project.Permissions.VIEW_PRIVATE_DATA,
        Project.Permissions.STAR_SOURCE_IMAGE,
    }


class Researcher(Role):
    permissions = BasicMember.permissions | {Project.Permissions.TRIGGER_EXPORT}


class Identifier(Role):
    permissions = BasicMember.permissions | {
        Project.Permissions.CREATE_IDENTIFICATION,
        Project.Permissions.UPDATE_IDENTIFICATION,
        Project.Permissions.DELETE_IDENTIFICATION,
    }


class MLDataManager(Role):
    permissions = BasicMember.permissions | {
        Project.Permissions.CREATE_JOB,
        Project.Permissions.UPDATE_JOB,
        Project.Permissions.RUN_JOB,
        Project.Permissions.RETRY_JOB,
        Project.Permissions.CANCEL_JOB,
        Project.Permissions.DELETE_JOB,
        Project.Permissions.DELETE_OCCURRENCES,
    }


class ProjectManager(Role):
    permissions = (
        BasicMember.permissions
        | Researcher.permissions
        | Identifier.permissions
        | MLDataManager.permissions
        | {
            Project.Permissions.CHANGE,
            Project.Permissions.CHANGE,
            Project.Permissions.DELETE,
            Project.Permissions.IMPORT_DATA,
            Project.Permissions.MANAGE_MEMBERS,
            Project.Permissions.POPULATE_COLLECTION,
            Project.Permissions.CREATE_COLLECTION,
            Project.Permissions.DELETE_COLLECTION,
            Project.Permissions.UPDATE_COLLECTION,
            Project.Permissions.CREATE_STORAGE,
            Project.Permissions.UPDATE_STORAGE,
            Project.Permissions.DELETE_STORAGE,
            Project.Permissions.CREATE_DEPLOYMENT,
            Project.Permissions.UPDATE_DEPLOYMENT,
            Project.Permissions.DELETE_DEPLOYMENT,
            Project.Permissions.CREATE_SITE,
            Project.Permissions.UPDATE_SITE,
            Project.Permissions.DELETE_SITE,
            Project.Permissions.CREATE_DEVICE,
            Project.Permissions.UPDATE_DEVICE,
            Project.Permissions.DELETE_DEVICE,
            Project.Permissions.CREATE_SOURCE_IMAGE,
            Project.Permissions.DELETE_SOURCE_IMAGE,
            Project.Permissions.UPDATE_SOURCE_IMAGE,
            Project.Permissions.CREATE_SOURCE_IMAGE_UPLOAD,
            Project.Permissions.UPDATE_SOURCE_IMAGE_UPLOAD,
            Project.Permissions.DELETE_SOURCE_IMAGE_UPLOAD,
        }
    )


def create_roles_for_project(project):
    """Creates role-based permission groups for a given project."""
    project_ct = ContentType.objects.get_for_model(Project)

    for role_class in Role.__subclasses__():
        role_name = f"{project.pk}_{project.name}_{role_class.__name__}"
        permissions = role_class.permissions
        group, created = Group.objects.get_or_create(name=role_name)
        if created:
            logger.debug(f"Role created {role_class} for project {project}")
        else:
            # Reset permissions to make sure permissions are updated
            # every time we call this function
            group.permissions.clear()
            assigned_perms = get_perms(group, project)
            for perm_codename in assigned_perms:
                remove_perm(perm_codename, group, project)
        for perm_codename in permissions:
            permission, perm_created = Permission.objects.get_or_create(
                codename=perm_codename,
                content_type=project_ct,
                defaults={"name": f"Can {perm_codename.replace('_', ' ')}"},
            )

            group.permissions.add(permission)  # Assign the permission group to the project
            assign_perm(perm_codename, group, project)
