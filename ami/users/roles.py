import logging

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import assign_perm

from ami.main.models import Project

logger = logging.getLogger(__name__)


class Role:
    """Base class for all roles."""

    permissions = {Project.Permissions.VIEW}

    @classmethod
    def assign_user(cls, user, project):
        # Get or create the Group
        group_name = f"{project.pk}_{project.name}_{cls.__name__}"
        group, created = Group.objects.get_or_create(name=group_name)
        # Add user to group
        user.groups.add(group)

    @classmethod
    def unassign_user(cls, user, project):
        group_name = f"{project.pk}_{project.name}_{cls.__name__}"
        group = Group.objects.get(name=group_name)
        # remove user from group
        user.groups.remove(group)

    @classmethod
    def has_role(cls, user, project):
        """Checks if the user has the role permissions on the given project."""
        group_name = f"{project.pk}_{project.name}_{cls.__name__}"

        return (
            all(user.has_perm(perm, project) for perm in cls.permissions)
            or user.groups.filter(name=group_name).exists()
        )


class BasicMember(Role):
    permissions = Role.permissions | {
        Project.Permissions.VIEW_PRIVATE_DATA,
        Project.Permissions.CHANGE,
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
            logger.info(f"Role created {role_class} for project {project}")
        for perm_codename in permissions:
            permission, perm_created = Permission.objects.get_or_create(
                codename=perm_codename,
                content_type=project_ct,
                defaults={"name": f"Can {perm_codename.replace('_', ' ')}"},
            )

            group.permissions.add(permission)  # Assign the permission group to the project
            assign_perm(perm_codename, group, project)
