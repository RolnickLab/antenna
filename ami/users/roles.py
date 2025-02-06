from django.contrib.auth.models import Group
from guardian.shortcuts import assign_perm, remove_perm

from ami.main.models import Project


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
        # Assign permissions
        for perm in cls.permissions:
            assign_perm(perm, user, project)

    @classmethod
    def unassign_user(cls, user, project):
        group_name = f"{project.pk}_{project.name}_{cls.__name__}"
        group = Group.objects.get(name=group_name)
        # remove user from group
        user.groups.remove(group)
        # remove permissions
        for perm in cls.permissions:
            remove_perm(perm, user, project)


class BasicMember(Role):
    permissions = Role.permissions | {Project.Permissions.VIEW_PRIVATE_DATA, Project.Permissions.CHANGE}


class Researcher(Role):
    permissions = BasicMember.permissions | {Project.Permissions.TRIGGER_EXPORT}


class Identifier(Role):
    permissions = BasicMember.permissions | {Project.Permissions.UPDATE_IDENTIFICATIONS}


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
            Project.Permissions.ADD,
            Project.Permissions.CHANGE,
            Project.Permissions.DELETE,
            Project.Permissions.ADD,
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
