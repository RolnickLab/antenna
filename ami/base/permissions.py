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
    user: AbstractBaseUser | AnonymousUser,
    instance: BaseModel,
    response_data: dict,
    cached_project_perms: set[str] | None = None,
) -> dict:
    """
    Adds object-level permissions to the response data for a given user and instance.
    This function updates the `response_data` dictionary with the permissions that the
    specified `user` has on the given `instance`'s project.

    Args:
        user: The user to check permissions for
        instance: The model instance to check permissions on
        response_data: The response dictionary to add permissions to
        cached_project_perms: Optional pre-fetched project permissions to avoid N+1 queries
    """

    permissions = response_data.get("user_permissions", set())
    if isinstance(instance, BaseModel):
        permissions.update(instance.get_user_object_permissions(user, cached_project_perms=cached_project_perms))
    response_data["user_permissions"] = list(permissions)
    return response_data


def add_collection_level_permissions(user: User | None, response_data: dict, model, project) -> dict:
    """Add collection-level permissions to the response data for a list view.

    This function modifies the `response_data` dictionary to include user permissions
    for creating new objects of the specified model type. If the user is logged in and
    is an active staff member, or if the user has create_model permission, the
    "create" permission is added to the `user_permissions` set in the `response_data`.

    Note: This is called once per pagination response, not per row, so it won't cause N+1.
    """
    logger.debug(f"add_collection_level_permissions model {model.__name__}, {type(model)} ")
    permissions = response_data.get("user_permissions", set())

    if not user or not user.is_authenticated:
        response_data["user_permissions"] = list(permissions)
        return response_data

    if user.is_superuser:
        permissions.add("create")
        response_data["user_permissions"] = list(permissions)
        return response_data

    if project:
        # get_perms is cached by django-cachalot, so this won't cause N+1
        perms = set(get_perms(user, project))
        if f"create_{model.__name__.lower()}" in perms:
            permissions.add("create")

    response_data["user_permissions"] = list(permissions)
    return response_data


class ObjectPermission(permissions.BasePermission):
    """
    Generic permission class that delegates to the model's `check_permission(user, action)` method.
    """

    def has_permission(self, request, view):
        return True  # Always allow — object-level handles actual checks

    def has_object_permission(self, request, view, obj: BaseModel):
        return obj.check_permission(request.user, view.action)
