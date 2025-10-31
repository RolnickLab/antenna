import logging

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import assign_perm, get_perms, remove_perm

from ami.main.models import Project

logger = logging.getLogger(__name__)


class Role:
    """Base class for all roles."""

    object_level_permissions = {Project.Permissions.VIEW_PROJECT}

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
        """
        Determine whether a user has any role for the given project.
        
        Returns:
            True if the user has at least one role for the project, False otherwise.
        """
        return any(role_class.has_role(user, project) for role_class in Role.__subclasses__())


class GlobalRole:
    """Base class for model-level roles."""

    model_level_permissions: set[str] = set()

    @classmethod
    def get_group_name(cls):
        """
        Return the group name used to represent this role at the model level.
        
        Returns:
            group_name (str): Group name derived from the role class's name.
        """
        return cls.__name__

    @classmethod
    def assign_user(cls, user):
        """
        Ensure the global role's group exists, grant that group the role's model-level permissions, and add the given user to the group.
        
        Parameters:
            user (django.contrib.auth.models.User): The user to assign to this global role's group.
        """
        group, created = Group.objects.get_or_create(name=cls.get_group_name())
        if created:
            logger.info(f"Created global permission group {cls.get_group_name()}")
        else:
            logger.info(f"Global permission group {cls.get_group_name()} already exists")
        cls.assign_model_level_permissions(group)
        user.groups.add(group)

    @classmethod
    def unassign_user(cls, user):
        """
        Remove a user from the global permission group associated with this role class.
        
        Parameters:
            user (django.contrib.auth.models.User): The user to remove from the role's global group.
        """
        group, _ = Group.objects.get_or_create(name=cls.get_group_name())
        user.groups.remove(group)

    @classmethod
    def assign_model_level_permissions(cls, group):
        """
        Ensure each codename in the class's `model_level_permissions` exists for the Project model and add those Permission objects to the provided group.
        
        For each permission codename in `cls.model_level_permissions`, this creates the corresponding Permission (using the Project content type and a human-readable name if needed) and attaches it to `group.permissions`.
        
        Parameters:
            group (django.contrib.auth.models.Group): The Django group that will receive the model-level permissions.
        """
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(Project)
        for perm_codename in cls.model_level_permissions:
            perm_codename = f"{perm_codename}"
            perm, _ = Permission.objects.get_or_create(
                codename=perm_codename,
                content_type=ct,
                defaults={"name": f"Can {perm_codename.replace('_', ' ')}"},
            )
            logger.info(f"Assigning model-level permission {perm_codename} to group {group.name}")
            group.permissions.add(perm)


class BasicMember(Role):
    object_level_permissions = Role.object_level_permissions | {
        Project.Permissions.VIEW_PRIVATE_DATA,
        Project.Permissions.STAR_SOURCE_IMAGE,
        Project.Permissions.CREATE_JOB,
        Project.Permissions.RUN_SINGLE_IMAGE_JOB,
    }


class Researcher(Role):
    object_level_permissions = BasicMember.object_level_permissions | {Project.Permissions.TRIGGER_EXPORT}


class Identifier(Role):
    object_level_permissions = BasicMember.object_level_permissions | {
        Project.Permissions.CREATE_IDENTIFICATION,
        Project.Permissions.UPDATE_IDENTIFICATION,
        Project.Permissions.DELETE_IDENTIFICATION,
    }


class MLDataManager(Role):
    object_level_permissions = BasicMember.object_level_permissions | {
        Project.Permissions.CREATE_JOB,
        Project.Permissions.UPDATE_JOB,
        # RUN ML jobs is revoked for now
        # Project.Permissions.RUN_ML_JOB,
        Project.Permissions.RUN_POPULATE_CAPTURES_COLLECTION_JOB,
        Project.Permissions.RUN_DATA_STORAGE_SYNC_JOB,
        Project.Permissions.RUN_DATA_EXPORT_JOB,
        Project.Permissions.DELETE_JOB,
        Project.Permissions.DELETE_OCCURRENCES,
    }


class ProjectManager(Role):
    object_level_permissions = (
        BasicMember.object_level_permissions
        | Researcher.object_level_permissions
        | Identifier.object_level_permissions
        | MLDataManager.object_level_permissions
        | {
            Project.Permissions.UPDATE_PROJECT,
            Project.Permissions.DELETE_PROJECT,
            Project.Permissions.IMPORT_DATA,
            Project.Permissions.MANAGE_MEMBERS,
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
        }
    )


class AuthorizedUser(GlobalRole):
    """A role that grants project create permission to all authenticated users."""

    model_level_permissions = {Project.Permissions.CREATE_PROJECT}


def create_roles_for_project(project):
    """
    Create or refresh role-based permission groups for the given project.
    
    For each subclass of Role, ensures a group named "<project.pk>_<project.name>_<RoleClassName>" exists, synchronizes the group's object-level permissions to the role's `object_level_permissions`, and assigns those permissions to the group for the specific project (project-scoped). Existing groups have their permissions cleared and project-scoped permissions removed before reassigning to reflect the current role definitions.
    
    Parameters:
        project (Project): The Project instance for which role groups and permissions should be created or updated.
    """
    project_ct = ContentType.objects.get_for_model(Project)

    for role_class in Role.__subclasses__():
        role_name = f"{project.pk}_{project.name}_{role_class.__name__}"
        object_level_permissions = role_class.object_level_permissions
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
        for perm_codename in object_level_permissions:
            permission, perm_created = Permission.objects.get_or_create(
                codename=perm_codename,
                content_type=project_ct,
                defaults={"name": f"Can {perm_codename.replace('_', ' ')}"},
            )

            group.permissions.add(permission)  # Assign the permission group to the project
            assign_perm(perm_codename, group, project)