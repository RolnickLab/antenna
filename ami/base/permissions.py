from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from guardian.shortcuts import get_perms
from rest_framework import permissions

from ami.main.models import Project

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


class ProjectCRUDPermissions(permissions.BasePermission):
    """A single permission class to handle Create, Retrieve, Update, and Delete permissions for Projects."""

    def has_permission(self, request, view):
        """Handles permissions at the global level (before accessing an object)."""

        # Allow all users to retrieve projects
        if view.action == "retrieve":
            return True

        # Create permission (only staff, superusers, or users with ADD permission)
        if view.action == "create":
            return request.user.is_staff or request.user.is_superuser or request.user.has_perm(Project.Permissions.ADD)

        return True  # Allow other actions (handled at object level)

    def has_object_permission(self, request, view, obj):
        """Handles permissions at the object level (for retrieve, update and delete)."""

        # Allow all users to retrieve projects
        if view.action == "retrieve":
            return True

        # Update permission (check CHANGE permission on the object)
        if view.action in ["update", "partial_update"]:
            return request.user.has_perm(Project.Permissions.CHANGE, obj)

        # Delete permission (check DELETE permission on the object)
        if view.action == "destroy":
            return request.user.has_perm(Project.Permissions.DELETE, obj)

        return False  # Default deny


class ProjectPermission(permissions.BasePermission):
    permission = Project.Permissions.VIEW

    def has_permission(self, request, view):
        if view.action == "create":
            project = view.get_active_project() if hasattr(view, "get_active_project") else None
            if project:
                return request.user.has_perm(self.permission, project)
        return True

    def has_object_permission(self, request, view, obj):
        # Get object's project
        project = obj.get_project()

        if not project:
            # If the object does have a project, try get from url or query params
            project = view.get_active_project()
        if project:
            return request.user.has_perm(self.permission, project)
        return True


class CanUpdateIdentification(ProjectPermission):
    """Custom permission to check if the user can update an identification."""

    permission = Project.Permissions.UPDATE_IDENTIFICATIONS


class CanDeleteOccurrence(ProjectPermission):
    """Custom permission to check if the user can delete an occurrence."""

    permission = Project.Permissions.DELETE_OCCURRENCES


class CanCreateJob(ProjectPermission):
    """Custom permission to check if the user can create a job."""

    permission = Project.Permissions.CREATE_JOB


class CanRunJob(ProjectPermission):
    """Custom permission to check if the user can run a job."""

    permission = Project.Permissions.RUN_JOB
