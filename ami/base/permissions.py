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


def user_can_manage_public_taxalist(user: AbstractBaseUser | AnonymousUser) -> bool:
    """A superuser, or a user holding the platform-wide manage_public_taxalist permission."""
    if not user or not user.is_authenticated:
        return False
    return bool(user.is_superuser or user.has_perm("main.manage_public_taxalist"))  # type: ignore[union-attr]


def check_taxalist_write_permission(user, taxa_list, project) -> bool:
    """
    True if `user` may update/delete `taxa_list` or change its taxa.

    A public list requires the platform-wide manage_public_taxalist permission
    (superusers always pass); a project-scoped list requires membership of `project`.
    """
    if user.is_superuser:
        return True
    if getattr(taxa_list, "is_public", False):
        return user.has_perm("main.manage_public_taxalist")
    return bool(project and project.members.filter(pk=user.pk).exists())


def add_m2m_object_permissions(user, instance, project, response_data: dict) -> dict:
    """
    Add object-level permissions for models with an M2M relationship to Project.

    The default permission resolution (BaseModel._get_object_perms) relies on
    get_project(), which returns None for M2M-to-Project models (TaxaList, etc.)
    because there's no single owning project. This function resolves permissions
    against a specific project from the request context instead.

    Validates that the instance actually belongs to the given project before
    granting any permissions (prevents cross-project permission leaks). A public
    instance is the one exception: its update/delete permissions come from the
    platform-wide manage_public_taxalist permission, not project membership.

    This is a temporary approach for the M2M permission gap described in #1120.
    Once that issue is resolved, this should be replaced by a generic permission
    class (Pattern B: Bare M2M) that handles TaxaList, Taxon, ProcessingService,
    Pipeline, and other M2M-to-Project models uniformly.
    """
    perms = set(response_data.get("user_permissions", []))

    if getattr(instance, "is_public", False):
        if user_can_manage_public_taxalist(user):
            perms.update(["update", "delete"])
        response_data["user_permissions"] = list(perms)
        return response_data

    if not project or not instance.projects.filter(pk=project.pk).exists():
        response_data["user_permissions"] = list(perms)
        return response_data

    if user.is_superuser:
        perms.update(["update", "delete"])
    else:
        model_name = instance._meta.model_name
        all_perms = get_perms(user, project)
        for perm in all_perms:
            if perm.endswith(f"_{model_name}"):
                action = perm.split("_", 1)[0]
                if action in {"update", "delete"}:
                    perms.add(action)

    response_data["user_permissions"] = list(perms)
    return response_data


class IsProjectMemberOrReadOnly(permissions.BasePermission):
    """
    Safe methods are allowed for everyone.
    Unsafe methods (POST, PUT, PATCH, DELETE) require the requesting user to be
    a member of the active project (resolved via ProjectMixin.get_active_project).
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:  # type: ignore[union-attr]
            return True

        # view must provide get_active_project (i.e. use ProjectMixin)
        get_active_project = getattr(view, "get_active_project", None)
        if not get_active_project:
            return False

        project = get_active_project()
        if not project:
            return False

        return project.members.filter(pk=request.user.pk).exists()


class IsProjectMemberOrPublicListManager(permissions.BasePermission):
    """
    Like IsProjectMemberOrReadOnly, but a user holding the platform-wide
    manage_public_taxalist permission also passes, regardless of project
    membership — for actions that can only ever land on a public list (adding
    or removing a taxon from an existing TaxaList via the nested route).
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser or user_can_manage_public_taxalist(request.user):  # type: ignore[union-attr]
            return True

        get_active_project = getattr(view, "get_active_project", None)
        if not get_active_project:
            return False

        project = get_active_project()
        if not project:
            return False

        return project.members.filter(pk=request.user.pk).exists()


class IsProjectMemberOrPublicListManagerOrReadOnly(IsProjectMemberOrPublicListManager):
    """
    For TaxaListViewSet: creating a brand-new list is always project-scoped and
    needs real project membership (there's no object yet to tell whether it will
    be public). Update/delete defer to the object-level check below, which grants
    the manage_public_taxalist bypass only once the target list's is_public flag
    is known — closing the gap where a project member could edit a public list
    just by supplying their own project_id.
    """

    def has_permission(self, request, view):
        if getattr(view, "action", None) == "create":
            return IsProjectMemberOrReadOnly.has_permission(self, request, view)
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        project = view.get_active_project() if hasattr(view, "get_active_project") else None
        return check_taxalist_write_permission(request.user, obj, project)


class ObjectPermission(permissions.BasePermission):
    """
    Generic permission class that delegates to the model's `check_permission(user, action)` method.
    """

    def has_permission(self, request, view):
        return True  # Always allow — object-level handles actual checks

    def has_object_permission(self, request, view, obj: BaseModel):
        return obj.check_permission(request.user, view.action)


class ProjectPipelineConfigPermission(ObjectPermission):
    """
    Permission for the nested project pipelines route (/projects/{pk}/pipelines/).

    Extends ObjectPermission to handle list/create actions where no object exists yet.
    Creates a temporary ProjectPipelineConfig instance to leverage BaseModel.check_permission(),
    which handles draft project visibility and guardian permission checks automatically.

    Follows the same pattern as UserMembershipPermission.
    """

    def has_permission(self, request, view):
        from ami.ml.models.project_pipeline_config import ProjectPipelineConfig

        if view.action in ("list", "create"):
            project = view.get_active_project()
            if not project:
                return False

            config = ProjectPipelineConfig(project=project)
            action = "retrieve" if view.action == "list" else "create"
            return config.check_permission(request.user, action)

        return super().has_permission(request, view)


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
