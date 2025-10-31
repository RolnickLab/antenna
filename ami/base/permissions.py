from __future__ import annotations

import logging

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser, User
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
    Add object-level permissions for `user` on `instance` into `response_data`.
    
    Retrieves existing `user_permissions` from `response_data` (defaults to an empty set), adds permissions returned by `instance.get_permissions(user)` when `instance` is a BaseModel, stores the resulting permissions as a list under `user_permissions`, and returns the updated `response_data`.
    
    Parameters:
        user (AbstractBaseUser | AnonymousUser): The user for whom permissions are collected.
        instance (BaseModel): The model instance whose object-level permissions are queried.
        response_data (dict): Response dictionary to be augmented; may already contain a `user_permissions` entry.
    
    Returns:
        dict: The updated `response_data` with `user_permissions` set to a list of permission strings.
    """

    permissions = response_data.get("user_permissions", set())
    if isinstance(instance, BaseModel):
        permissions.update(instance.get_permissions(user))
    response_data["user_permissions"] = list(permissions)
    return response_data


def add_collection_level_permissions(user: User | None, response_data: dict, model, project) -> dict:
    """
    Add collection-level permissions for a model to the response payload for a list view.
    
    Queries the model for collection-level permissions for the given user and project, merges them into the response_data's "user_permissions" entry, and returns the updated response_data.
    
    Parameters:
        user (User | None): The requesting user or None for anonymous requests.
        response_data (dict): The response payload to augment; its "user_permissions" key will be updated.
        model: The model class providing collection-level permissions via a `get_collection_level_permissions(user, project)` method.
        project: The project context passed to the model's permission lookup.
    
    Returns:
        dict: The updated response_data with "user_permissions" set to a list of permission strings.
    """

    logger.info(f"add_collection_level_permissions model {model.__name__}, {type(model)} ")
    permissions = response_data.get("user_permissions", set())
    collection_level_perms = model.get_collection_level_permissions(user=user, project=project)
    permissions.update(collection_level_perms)
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