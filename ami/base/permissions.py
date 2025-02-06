from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from guardian.shortcuts import get_perms
from rest_framework import permissions

from ami.jobs.models import Job
from ami.main.models import Deployment, Device, Identification, Project, S3StorageSource, Site, SourceImageCollection

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
    Maps django default permissions to generic permissions compatible with the frontend.
    view_modelname -> view
    create_modelname -> create
    update_modelname -> update
    delete_modelname -> delete
    """
    permissions = get_perms(user, obj)
    result = [perm.split("_")[0] for perm in permissions]

    # allow view for all users
    if "view" not in result:
        result.append("view")
    return result


class CRUDPermission(permissions.BasePermission):
    """
    Generic CRUD permission class that dynamically checks user permissions on an object.
    Permission names follow the convention: `create_<model>`, `update_<model>`, `delete_<model>`.
    """

    model = None

    def has_permission(self, request, view):
        """Handles general permission checks"""

        model_name = self.model._meta.model_name
        # Permission name for creation
        if view.action == "create":
            return request.user.is_staff or request.user.is_superuser or request.user.has_perm(f"create_{model_name}")

        return True

    def has_object_permission(self, request, view, obj):
        """Handles object-level permission checks."""
        model_name = self.model._meta.model_name
        project = obj.get_project() if hasattr(obj, "get_project") else None

        # check for create action
        if view.action == "create":
            return (
                request.user.is_staff
                or request.user.is_superuser
                or request.user.has_perm(f"create_{model_name}", project)
            )

        if view.action == "retrieve":
            return True  # Allow all users to view objects

        # Map ViewSet actions to permission names
        action_perms = {
            "retrieve": f"view_{model_name}",
            "update": f"update_{model_name}",
            "partial_update": f"update_{model_name}",
            "destroy": f"delete_{model_name}",
        }

        required_perm = action_perms.get(view.action)
        if not required_perm:
            return True
        return request.user.has_perm(required_perm, project)


class ProjectCRUDPermission(CRUDPermission):
    model = Project


class JobCRUDPermission(CRUDPermission):
    model = Job


class DeploymentCRUDPermission(CRUDPermission):
    model = Deployment


class SourceImageCollectionCRUDPermission(CRUDPermission):
    model = SourceImageCollection


class S3StorageSourceCRUDPermission(CRUDPermission):
    model = S3StorageSource


class SiteCRUDPermission(CRUDPermission):
    model = Site


class DeviceCRUDPermission(CRUDPermission):
    model = Device


class IdentificationCRUDPermission(CRUDPermission):
    model = Identification


# Identification permission checks
class CanUpdateIdentification(permissions.BasePermission):
    """Custom permission to check if the user can update/create an identification."""

    permission = Project.Permissions.UPDATE_IDENTIFICATIONS

    def has_object_permission(self, request, view, obj):
        if view.action in ["create", "update", "partial_update"]:
            project = obj.get_project() if hasattr(obj, "get_project") else None
            return request.user.has_perm(self.permission, project)
        return True


class CanDeleteIdentification(permissions.BasePermission):
    """Custom permission to check if the user can delete an identification."""

    permission = Project.Permissions.DELETE_IDENTIFICATIONS

    def has_object_permission(self, request, view, obj):
        project = obj.get_project() if hasattr(obj, "get_project") else None
        if view.action == "destroy":
            if request.user.is_superuser or request.user.is_staff:
                return True
            # Check if the user has the required permission and is the owner of the object
            return obj.user == request.user and request.user.has_perm(self.permission, project)
        return True


# Job run permission check
class CanRunJob(permissions.BasePermission):
    """Custom permission to check if the user can run a job."""

    permission = Project.Permissions.RUN_JOB

    def has_object_permission(self, request, view, obj):
        if view.action == "run":
            project = obj.get_project() if hasattr(obj, "get_project") else None
            return request.user.has_perm(self.permission, project)
        return True


class CanRetryJob(permissions.BasePermission):
    """Custom permission to check if the user can retry a job."""

    permission = Project.Permissions.RETRY_JOB

    def has_object_permission(self, request, view, obj):
        if view.action == "retry":
            project = obj.get_project() if hasattr(obj, "get_project") else None
            return request.user.has_perm(self.permission, project)
        return True


class CanCancelJob(permissions.BasePermission):
    """Custom permission to check if the user can cancel a job."""

    permission = Project.Permissions.CANCEL_JOB

    def has_object_permission(self, request, view, obj):
        if view.action == "cancel":
            project = obj.get_project() if hasattr(obj, "get_project") else None
            return request.user.has_perm(self.permission, project)
        return True


class CanPopulateCollection(permissions.BasePermission):
    """Custom permission to check if the user can populate a collection."""

    permission = Project.Permissions.POPULATE_COLLECTION

    def has_object_permission(self, request, view, obj):
        if view.action == "populate":
            project = obj.get_project() if hasattr(obj, "get_project") else None
            return request.user.has_perm(self.permission, project)
        return True
