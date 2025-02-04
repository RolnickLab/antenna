from guardian.shortcuts import assign_perm, remove_perm

from ami.main.models import Project


class Role:
    """Base class for all roles."""

    permissions = {Project.Permissions.VIEW}

    @classmethod
    def assign_user(cls, user, project):
        for perm in cls.permissions:
            assign_perm(perm, user, project)

    @classmethod
    def un_assign_user(cls, user, project):
        for perm in cls.permissions:
            remove_perm(perm, user, project)


class BasicMember(Role):
    permissions = Role.permissions | {Project.Permissions.VIEW_PRIVATE_DATA}


class Researcher(Role):
    permissions = BasicMember.permissions | {Project.Permissions.TRIGGER_EXPORT}


class Identifier(Role):
    permissions = BasicMember.permissions | {Project.Permissions.UPDATE_IDENTIFICATIONS}


class MLDataManager(Role):
    permissions = BasicMember.permissions | {
        Project.Permissions.CREATE_JOB,
        Project.Permissions.RUN_JOB,
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
        }
    )
