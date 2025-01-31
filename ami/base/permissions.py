from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from guardian.shortcuts import get_perms
from rest_framework import permissions

logger = logging.getLogger(__name__)
if TYPE_CHECKING:
    from django.contrib.auth.models import User


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


def add_object_level_permissions(user, project, response_data: dict) -> dict:
    """
    Add placeholder permissions to detail views and nested objects.

    If the user is logged in, they can edit any object type.
    If the user is a superuser, they can delete any object type.

    @TODO @IMPORTANT At least check if they are the owner of the project.
    """

    permissions = response_data.get("user_permissions", set())

    if user and is_active_staff(user):
        permissions.update(["update"])
        if user.is_superuser:
            permissions.update(["delete"])
    if project:
        user_permissions = get_generic_permissions(user, project)
        permissions.update(set(user_permissions))

    response_data["user_permissions"] = permissions
    return response_data


def add_collection_level_permissions(user: User | None, response_data: dict) -> dict:
    """
    Add placeholder permissions to list view responses.

    If the user is logged in, they can create new objects of any type.
    """
    permissions = response_data.get("user_permissions", set())
    if user and is_active_staff(user):
        permissions.add("create")
    response_data["user_permissions"] = permissions
    return response_data


def get_generic_permissions(user, obj):
    """
    Maps django default permissions to generic permissions
    view_modelname -> view
    add_modelname -> create
    change_modelname -> update
    delete_modelname -> delete
    """
    permissions = get_perms(user, obj)
    mapping = {"view": "view", "change": "update", "add": "create", "delete": "delete"}
    result = []
    for perm in permissions:
        if perm.split("_")[0] in mapping:
            result.append(mapping[perm.split("_")[0]])
        else:
            result.append(perm)

    # allow view for all users
    if "view" not in result:
        result.append("view")
    return result


class ObjectPermissions(permissions.BasePermission):
    """
    Object-level permission checking with django-guardian.
    Maps DRF actions ('create', 'retrieve', etc.) to guardian permissions.
    """

    def has_permission(self, request, view):
        # Only allow active staff users to create a project
        if view.action == "create":
            return is_active_staff(request.user)
        return True  # Fallback to object-level checks

    def has_object_permission(self, request, view, obj):
        user = request.user
        permissions = get_generic_permissions(user, obj)

        # Map ViewSet actions to permissions
        view_action_map = {
            "retrieve": "view",
            "update": "update",
            "partial_update": "update",
            "destroy": "delete",
        }
        # Get the required permission for the current action
        perm = view_action_map.get(view.action)
        if not perm:
            return False  # Deny by default for unmapped actions
        # Check if the user has the permission for this object
        return perm in permissions
