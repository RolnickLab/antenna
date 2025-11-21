from __future__ import annotations

import logging

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser, User
from guardian.shortcuts import get_perms
from rest_framework import permissions

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

    permissions = response_data.get("user_permissions", set())
    if isinstance(instance, BaseModel):
        permissions.update(instance.get_user_object_permissions(user))
    response_data["user_permissions"] = list(permissions)
    return response_data


def add_collection_level_permissions(user: User | None, response_data: dict, model, project) -> dict:
    """Add collection-level permissions to the response data for a list view.

    This function modifies the `response_data` dictionary to include user permissions
    for creating new objects of the specified model type. If the user is logged in and
    is an active staff member, or if the user has create_model permission, the
    "create" permission is added to the `user_permissions` set in the `response_data`.
    """

    logger.debug(f"add_collection_level_permissions model {model.__name__}, {type(model)} ")
    permissions = response_data.get("user_permissions", set())
    if user and user.is_superuser:
        permissions.add("create")
    if user and project and f"create_{model.__name__.lower()}" in get_perms(user, project):
        permissions.add("create")
    response_data["user_permissions"] = list(permissions)
    return response_data


class ProjectMemberPermissions(permissions.BasePermission):
    """
    Controls access to project member api operations.

    Rules:
    - READ (GET/list): user must be a project member (BasicMember or higher)
    - WRITE (POST/PUT): user must be a ProjectManager
    - DELETE: user must be a ProjectManager OR user is removing themselves AND is a member
    """

    def has_permission(self, request, view):
        from ami.users.roles import ProjectManager, Role

        project = view.get_active_project()
        user = request.user

        if project is None:
            return False

        # READ permissions
        if request.method in permissions.SAFE_METHODS:
            return Role.user_has_any_role(user, project)

        # WRITE permissions
        # Allow if user is project manager
        if ProjectManager.has_role(user, project):
            return True

        # User is removing themselves
        if view.action == "destroy":
            target_user_id = view.kwargs.get("pk")
            if target_user_id and str(user.pk) == str(target_user_id):
                # Only allow if the user is at least a BasicMember
                return Role.user_has_any_role(user, project)

        return False

    def has_object_permission(self, request, view, obj):
        # Object-level permissions are handled in has_permission
        return True


class ObjectPermission(permissions.BasePermission):
    """
    Generic permission class that delegates to the model's `check_permission(user, action)` method.
    """

    def has_permission(self, request, view):
        return True  # Always allow — object-level handles actual checks

    def has_object_permission(self, request, view, obj: BaseModel):
        return obj.check_permission(request.user, view.action)
