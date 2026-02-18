import logging

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import assign_perm, get_perms, remove_perm

from ami.main.models import Project

logger = logging.getLogger(__name__)


class Role:
    """Base class for all roles."""

    display_name = ""
    description = ""
    permissions = {Project.Permissions.VIEW_PROJECT}

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

    @staticmethod
    def get_supported_roles():
        """
        Returns all supported role classes in the system.
        """
        return list(Role.__subclasses__())

    @staticmethod
    def get_user_roles(project, user):
        """
        Returns the names of roles assigned to a user for a specific project.
        Or empty list if no role is found.
        """
        user_roles = []
        for role_cls in Role.__subclasses__():
            if role_cls.has_role(user, project):
                user_roles.append(role_cls)
        return user_roles

    @staticmethod
    def get_primary_role(project, user):
        """
        Return the role class with the most permissions for a user on a project.

        In practice, a user should only have one role per project, but in case of multiple roles,
        we return the one with the most permissions.

        The original design allowed multiple roles per user per project, but it was later decided to
        that from a UX and management perspective, a single role per user per project is preferable.
        """
        roles = Role.get_user_roles(project, user)
        if not roles:
            return None
        return max(roles, key=lambda r: len(r.permissions))


class BasicMember(Role):
    display_name = "Basic member"
    description = (
        "Basic project member with access to star source images, create jobs, and run single image processing jobs."
    )
    permissions = Role.permissions | {
        Project.Permissions.VIEW_PRIVATE_DATA,
        Project.Permissions.STAR_SOURCE_IMAGE,
        Project.Permissions.CREATE_JOB,
        Project.Permissions.RUN_SINGLE_IMAGE_JOB,
        Project.Permissions.VIEW_USER_PROJECT_MEMBERSHIP,
    }


class Researcher(Role):
    display_name = "Researcher"
    description = "Researcher with all basic member permissions, plus the ability to create and delete data exports"
    # Note: UPDATE_DATA_EXPORT is intentionally excluded - only superusers can modify exports.
    # Users should delete and recreate exports if they need different settings.
    permissions = BasicMember.permissions | {
        Project.Permissions.CREATE_DATA_EXPORT,
        Project.Permissions.DELETE_DATA_EXPORT,
    }


class Identifier(Role):
    display_name = "Identifier"
    description = (
        "Identifier with all basic member permissions, plus the ability to create, "
        "update, and delete occurrence identifications."
    )
    permissions = BasicMember.permissions | {
        Project.Permissions.CREATE_IDENTIFICATION,
        Project.Permissions.UPDATE_IDENTIFICATION,
        Project.Permissions.DELETE_IDENTIFICATION,
    }


class MLDataManager(Role):
    display_name = "ML Data manager"
    description = (
        "Machine Learning Data Manager with all basic member permissions, plus the ability to "
        "manage ML jobs, run collection population jobs, sync data storage, export data, and "
        "delete occurrences."
    )
    permissions = BasicMember.permissions | {
        Project.Permissions.CREATE_JOB,
        Project.Permissions.UPDATE_JOB,
        # RUN ML jobs is revoked for now
        # Project.Permissions.RUN_ML_JOB,
        Project.Permissions.RUN_POPULATE_CAPTURES_COLLECTION_JOB,
        Project.Permissions.RUN_DATA_STORAGE_SYNC_JOB,
        Project.Permissions.RUN_DATA_EXPORT_JOB,
        Project.Permissions.DELETE_JOB,
        Project.Permissions.DELETE_OCCURRENCES,
        Project.Permissions.CREATE_PROJECT_PIPELINE_CONFIG,
    }


class ProjectManager(Role):
    display_name = "Project manager"
    description = (
        "Project manager with full administrative access, including all permissions from all roles "
        "plus the ability to manage project settings, members, deployments, collections, storage, "
        "and all project resources."
    )
    permissions = (
        BasicMember.permissions
        | Researcher.permissions
        | Identifier.permissions
        | MLDataManager.permissions
        | {
            Project.Permissions.UPDATE_PROJECT,
            Project.Permissions.DELETE_PROJECT,
            Project.Permissions.IMPORT_DATA,
            Project.Permissions.POPULATE_COLLECTION,
            Project.Permissions.CREATE_COLLECTION,
            Project.Permissions.DELETE_COLLECTION,
            Project.Permissions.UPDATE_COLLECTION,
            Project.Permissions.CREATE_STORAGE,
            Project.Permissions.UPDATE_STORAGE,
            Project.Permissions.DELETE_STORAGE,
            Project.Permissions.TEST_STORAGE,
            Project.Permissions.CREATE_DEPLOYMENT,
            Project.Permissions.UPDATE_DEPLOYMENT,
            Project.Permissions.DELETE_DEPLOYMENT,
            Project.Permissions.SYNC_DEPLOYMENT,
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
            Project.Permissions.CREATE_USER_PROJECT_MEMBERSHIP,
            Project.Permissions.UPDATE_USER_PROJECT_MEMBERSHIP,
            Project.Permissions.DELETE_USER_PROJECT_MEMBERSHIP,
            Project.Permissions.CREATE_PROJECT_PIPELINE_CONFIG,
            Project.Permissions.UPDATE_PROJECT_PIPELINE_CONFIG,
            Project.Permissions.DELETE_PROJECT_PIPELINE_CONFIG,
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
