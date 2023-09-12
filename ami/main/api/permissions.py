from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import User


def add_object_level_permissions(user: User | None, response_data: dict) -> dict:
    """
    Add placeholder permissions to detail views and nested objects.

    If the user is logged in, they can edit any object type.
    If the user is a superuser, they can delete any object type.

    @TODO @IMPORTANT At least check if they are the owner of the project.
    """
    permissions = response_data.get("user_permissions", set())
    if user and user.is_authenticated:
        permissions.update(["update"])
        if user.is_superuser:
            permissions.update(["delete"])
    response_data["user_permissions"] = permissions
    return response_data


def add_collection_level_permissions(user: User | None, response_data: dict) -> dict:
    """
    Add placeholder permissions to list view responses.

    If the user is logged in, they can create new objects of any type.
    """
    permissions = response_data.get("user_permissions", set())
    if user and user.is_authenticated:
        permissions.add("create")
    response_data["user_permissions"] = permissions
    return response_data
