from __future__ import annotations

import logging
import typing

from django.contrib.auth.models import AbstractBaseUser, AbstractUser, AnonymousUser, User
from guardian.shortcuts import get_perms
from rest_framework import permissions

if typing.TYPE_CHECKING:
    from ami.main.models import BaseModel
logger = logging.getLogger(__name__)


def is_active_staff(user: User) -> bool:
    return bool(
        user.is_authenticated and user.is_staff and user.is_active,
    )


class IsActiveStaffOrReadOnly(permissions.BasePermission):
    """
    The request is by a staff member, or is a read-only request.
    """

    def has_permission(self, request, view):
        return bool(
            request.method in permissions.SAFE_METHODS
            or request.user
            and request.user.is_authenticated
            and is_active_staff(request.user)  # type: ignore # @TODO why?
        )


def filter_permissions(permissions, model_name):
    """Filter and extract only the action part of `action_modelname`"""

    filtered_permissions = {
        perm.split("_")[0]  # Extract "action" from "action_modelname"
        for perm in permissions
        if perm.endswith(f"_{model_name}")  # Ensure it matches the model
    }
    return filtered_permissions


def add_object_level_permissions(
    user: AbstractBaseUser | AnonymousUser, instance: BaseModel, response_data: dict
) -> dict:
    """
    Adds object-level permissions to the response data for a given user and instance.
    This function updates the `response_data` dictionary with the permissions that the
    specified `user` has on the given `instance`'s project.
    """
    from ami.base.models import BaseModel

    permissions = response_data.get("user_permissions", set())
    if isinstance(instance, BaseModel):
        permissions.update(instance.get_permissions(user))
    response_data["user_permissions"] = list(permissions)
    return response_data


def add_collection_level_permissions(user: User | None, response_data: dict, model, project) -> dict:
    """Add collection-level permissions to the response data for a list view.

    This function modifies the `response_data` dictionary to include user permissions
    for creating new objects of the specified model type. If the user is logged in and
    is an active staff member, or if the user has create_model permission, the
    "create" permission is added to the `user_permissions` set in the `response_data`.
    """

    logger.info(f"add_collection_level_permissions model {model.__name__}, {type(model)} ")
    permissions = response_data.get("user_permissions", set())
    collection_level_perms = model.get_collection_level_permissions(user=user, project=project)
    permissions.update(collection_level_perms)
    response_data["user_permissions"] = list(permissions)
    return response_data


class PermissionsMixin:
    """
    A mixin for `BaseModel` that provides methods to check and retrieve
    both object-level and model-level permissions, supporting standard
    CRUD actions as well as custom project-specific permissions.

    It integrates with Django’s permission framework and Django Guardian
    to handle global (model-level) and project-scoped (object-level) access
    control. This allows consistent permission checks across all models
    that inherit from `BaseModel`.
    """

    def _get_object_perms(self: BaseModel, user):  # type: ignore[override]
        """
        Get the object-level permissions for the user on this instance.
        This method retrieves permissions like `update_modelname`, `create_modelname`, etc.
        """
        project = self.get_project()
        if not project:
            return []

        model_name = self._meta.model_name
        all_perms = get_perms(user, project)
        object_perms = [perm for perm in all_perms if perm.endswith(f"_{model_name}")]
        return object_perms

    def check_model_level_permission(
        self: BaseModel, user: AbstractUser | AnonymousUser, action: str  # type: ignore[override]
    ) -> bool:
        model = self._meta.model_name
        app_label = "main"  # Assume all model level permissions are in 'main' app

        crud_map = {
            "create": f"{app_label}.create_{model}",
            "update": f"{app_label}.update_{model}",
            "partial_update": f"{app_label}.update_{model}",
            "destroy": f"{app_label}.delete_{model}",
            "retrieve": f"{app_label}.view_{model}",
        }

        perm = crud_map.get(action, f"{app_label}.{action}_{model}")
        if action == "retrieve":
            return True  # allow view permission for all users
        return user.has_perm(perm)

    def check_permission(
        self: BaseModel, user: AbstractUser | AnonymousUser, action: str  # type: ignore[override]
    ) -> bool:
        """
        Entry point for all permission checks.
        Decides whether to perform model-level or object-level permission check.
        """
        # Get related project accessor
        accessor = self.get_project_accessor()
        if accessor is None or accessor == "projects":
            # If there is no project relation, use model-level permission
            return self.check_model_level_permission(user, action)

        # If the object is linked to a project then use object-level permission
        return self.check_object_level_permission(user, action)

    def check_object_level_permission(
        self: BaseModel, user: AbstractUser | AnonymousUser, action: str  # type: ignore[override]
    ) -> bool:
        """
        Check if the user has permission to perform the action
        on this instance.
        This method is used to determine if the user can perform
        CRUD operations or custom actions on the model instance.
        """
        from ami.users.roles import BasicMember

        model = self._meta.model_name
        crud_map = {
            "create": f"create_{model}",
            "update": f"update_{model}",
            "partial_update": f"update_{model}",
            "destroy": f"delete_{model}",
        }

        project = self.get_project() if hasattr(self, "get_project") else None
        if not project:
            # No specific project instance found; fallback to model-level
            return self.check_model_level_permission(user, action)
        if action == "retrieve":
            if project.draft:
                # Allow view permission for members and owners of draft projects
                return BasicMember.has_role(user, project) or user == project.owner or user.is_superuser
            return True

        if action in crud_map:
            return user.has_perm(crud_map[action], project)

        # Delegate to model-specific logic
        return self.check_custom_object_level_permission(user, action)

    def check_custom_object_level_permission(self: BaseModel, user: AbstractUser | AnonymousUser, action: str) -> bool:
        """Check custom object level permissions for the user on this instance.
        This is used for actions that are not standard CRUD operations.
        """
        assert self._meta.model_name is not None, "Model must have a model_name defined in Meta class."
        model_name = self._meta.model_name.lower()
        permission_codename = f"{action}_{model_name}"
        project = self.get_project() if hasattr(self, "get_project") else None

        return user.has_perm(permission_codename, project)

    def get_permissions(self: BaseModel, user: AbstractUser | AnonymousUser) -> list[str]:  # type: ignore[override]
        """
        Entry point for retrieving user permissions on this instance.
        Decides whether to return model-level or object-level permissions.
        """
        accessor = self.get_project_accessor()

        if accessor is None or accessor == "projects":
            # M2M or no project relation, use model-level permissions
            return self.get_model_level_permissions(user)

        # Otherwise, get object-level permissions
        return self.get_object_level_permissions(user)

    def get_model_level_permissions(
        self: BaseModel, user: AbstractUser | AnonymousUser  # type: ignore[override]
    ) -> list[str]:
        """
        Retrieve model-level permissions for the given user.
        Returns a list of allowed actions such as ["create", "update", "delete"].
        """
        if user.is_superuser:
            # Superusers get all possible actions
            return ["update", "delete", "view"]

        model = self._meta.model_name
        app_label = "main"  # self._meta.app_label
        crud_map = {
            "update": f"{app_label}.update_{model}",
            "delete": f"{app_label}.delete_{model}",
            "view": f"{app_label}.view_{model}",
        }

        allowed_actions = [action for action, perm in crud_map.items() if user.has_perm(perm)]
        # Add any non-CRUD custom model-level permissions
        custom_actions = self.get_custom_model_level_permissions(user)
        allowed_actions.extend(custom_actions)

        return allowed_actions

    def get_custom_model_level_permissions(
        self: BaseModel, user: AbstractUser | AnonymousUser  # type: ignore[override]
    ) -> list[str]:
        """
        Retrieve custom (non-CRUD) model-level permissions for the given user.
        Custom permissions follow the pattern: <app_label>.<custom_action>_<model_name>
        Example: "main.register_pipelines_processingservice"
        """
        model = self._meta.model_name
        app_label = "main"

        user_perms = user.get_all_permissions()
        custom_actions = set()

        for perm in user_perms:
            if not perm.startswith(f"{app_label}."):
                continue
            try:
                _, perm_name = perm.split(".", 1)
                action, target_model = perm_name.rsplit("_", 1)
                if target_model == model and action not in {"view", "create", "update", "delete"}:
                    custom_actions.add(action)
            except ValueError:
                continue
        return list(custom_actions)

    def get_object_level_permissions(
        self: BaseModel, user: AbstractUser | AnonymousUser  # type: ignore[override]
    ) -> list[str]:
        """
        Retrieve object-level permissions (including custom ones) for this instance.
        """

        if user.is_superuser:
            return ["update", "delete"] + self.get_custom_object_level_permissions(user)

        project = self.get_project()
        if not project:
            # Fallback to model-level permissions if no related project found
            return self.get_model_level_permissions(user)

        object_perms = self._get_object_perms(user)
        allowed_actions = {
            perm.split("_", 1)[0] for perm in object_perms if perm.split("_", 1)[0] in {"update", "delete"}
        }

        custom_actions = self.get_custom_object_level_permissions(user)
        return list(allowed_actions.union(custom_actions))

    def get_custom_object_level_permissions(
        self: BaseModel, user: AbstractUser | AnonymousUser  # type: ignore[override]
    ) -> list[str]:
        """
        Retrieve custom (non-CRUD) permissions for this instance.
        """
        object_perms = self._get_object_perms(user)
        custom_perms = {
            perm.rsplit("_", 1)[0]
            for perm in object_perms
            if perm.split("_", 1)[0] not in ["view", "create", "update", "delete"]
        }
        return list(custom_perms)

    @classmethod
    def get_collection_level_permissions(
        cls: type[BaseModel], user: AbstractUser | AnonymousUser, project  # type: ignore
    ) -> list[str]:
        """
        Retrieve collection-level permissions for the given user.
        """
        app_label = "main"
        if user.is_superuser:
            return ["create"]
        # If the model is m2m related to projects or has no project relation, use model-level permissions
        if cls.get_project_accessor() is None or cls.get_project_accessor() == "projects":
            if user.has_perm(f"{app_label}.create_{cls._meta.model_name}"):
                return ["create"]
        # If the model is related to a single project, check create permission at object level
        if cls.get_project_accessor() is not None and project:
            if user.has_perm(f"{app_label}.create_{cls._meta.model_name}", project):
                return ["create"]

        return []


class ObjectPermission(permissions.BasePermission):
    """
    Generic permission class that delegates to the model's `check_permission(user, action)` method.
    """

    def has_permission(self, request, view):
        return True  # Always allow — object-level handles actual checks

    def has_object_permission(self, request, view, obj: BaseModel):
        return obj.check_permission(request.user, view.action)


class UserMembershipPermission(ObjectPermission):
    """
    Custom permission for UserProjectMembershipViewSet.

    The `list` action has no object to check against, so we treat it like a
    `retrieve` action: we fetch the active project, create a temporary
    membership object for it, and apply the same permission check. All other
    actions fall back to the default ObjectPermission logic.
    """

    def has_permission(self, request, view):
        # Special handling for the list action: treat it like retrieve action
        from ami.main.models import UserProjectMembership

        if view.action == "list":
            project = view.get_active_project()
            if not project:
                return False

            # Create an unsaved membership instance with only project set
            membership = UserProjectMembership(user=None, project=project)

            # Check whether the requesting user would be allowed to retrieve this
            return membership.check_permission(request.user, "retrieve")

        # Fallback to default ObjectPermission behavior
        return super().has_permission(request, view)
