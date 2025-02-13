from __future__ import annotations

import logging

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser, User
from guardian.shortcuts import get_perms
from rest_framework import permissions

from ami.jobs.models import Job
from ami.main.models import BaseModel, Deployment, Device, Project, S3StorageSource, Site, SourceImageCollection
from ami.users.roles import ProjectManager

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
    project = instance.get_project() if hasattr(instance, "get_project") else None
    model_name = instance._meta.model_name  # Get model name
    if user and is_active_staff(user):
        permissions.update(["update"])
        if user.is_superuser:
            permissions.update(["delete"])
    if project:
        user_permissions = get_perms(user, project)

        # Filter and extract only the action part of "action_modelname" based on instance type
        filtered_permissions = filter_permissions(permissions=user_permissions, model_name=model_name)
        permissions.update(filtered_permissions)
    response_data["user_permissions"] = permissions
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
    if user and is_active_staff(user):
        permissions.add("create")

    if user and project and f"create_{model.__name__.lower()}" in get_perms(user, project):
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


class CanStarSourceImage(permissions.BasePermission):
    """Custom permission to check if the user can star a Source image."""

    permission = Project.Permissions.STAR_SOURCE_IMAGE

    def has_object_permission(self, request, view, obj):
        if view.action in ["unstar", "star"]:
            project = obj.get_project() if hasattr(obj, "get_project") else None
            return request.user.has_perm(self.permission, project)
        return True


class S3StorageSourceCRUDPermission(CRUDPermission):
    model = S3StorageSource


class SiteCRUDPermission(CRUDPermission):
    model = Site


class DeviceCRUDPermission(CRUDPermission):
    model = Device


# Identification permission checks
class CanUpdateIdentification(permissions.BasePermission):
    """Custom permission to check if the user can update/create an identification."""

    permission = Project.Permissions.UPDATE_IDENTIFICATION

    def has_object_permission(self, request, view, obj):
        if view.action in ["create", "update", "partial_update"]:
            project = obj.get_project() if hasattr(obj, "get_project") else None
            return request.user.has_perm(self.permission, project)
        return True


class CanDeleteIdentification(permissions.BasePermission):
    """Custom permission to check if the user can delete an identification."""

    permission = Project.Permissions.DELETE_IDENTIFICATION

    def has_object_permission(self, request, view, obj):
        project = obj.get_project() if hasattr(obj, "get_project") else None
        # Check if user is superuser or staff or project manager
        if view.action == "destroy":
            if request.user.is_superuser or request.user.is_staff or ProjectManager.has_role(request.user, project):
                return True
            # Check if the user is the owner of the object
            return obj.user == request.user
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


class CanPopulateSourceImageCollection(permissions.BasePermission):
    """Custom permission to check if the user can populate a collection."""

    permission = Project.Permissions.POPULATE_COLLECTION

    def has_object_permission(self, request, view, obj):
        if view.action == "populate":
            project = obj.get_project() if hasattr(obj, "get_project") else None
            return request.user.has_perm(self.permission, project)
        return True
