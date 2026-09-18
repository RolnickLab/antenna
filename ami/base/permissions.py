from __future__ import annotations

import logging

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser, User
from guardian.shortcuts import get_perms
from rest_framework import exceptions, permissions

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


def user_can_manage_public(user: AbstractBaseUser | AnonymousUser, model_or_instance) -> bool:
    """
    A superuser, or a user holding <app_label>.manage_public_<model_name> for
    the given model (or an instance of it) — the platform permission gating
    write access to a public row, in place of project membership or staff status.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:  # type: ignore[union-attr]
        return True
    meta = model_or_instance._meta
    return user.has_perm(f"{meta.app_label}.manage_public_{meta.model_name}")  # type: ignore[union-attr]


def check_public_scoped_write_permission(user, instance, non_public_fallback) -> bool:
    """
    True if `user` may write to `instance`: a public row needs the platform
    manage_public_<model> permission (superusers always pass, via
    user_can_manage_public); a non-public row falls back to `non_public_fallback()`,
    the model's own write rule (project membership, active-staff status, ...).
    """
    if getattr(instance, "is_public", False):
        return user_can_manage_public(user, instance)
    return non_public_fallback()


def check_taxalist_write_permission(user, taxa_list, project) -> bool:
    """Thin alias kept so branches stacked on this one still import this name."""
    return check_public_scoped_write_permission(
        user, taxa_list, lambda: bool(user.is_superuser or (project and project.members.filter(pk=user.pk).exists()))
    )


def check_taxalist_not_managed(taxa_list) -> None:
    """
    Raise 403 if `taxa_list` is managed (at least one algorithm points at it — see
    `Algorithm.sync_taxa_list()`). Applies to every caller, including superusers and
    manage_public_taxalist holders, because the next sync would silently overwrite a
    hand edit. Guards taxon add/remove and list delete; renaming a managed list still
    goes through `check_taxalist_write_permission` as normal.
    """
    if getattr(taxa_list, "is_managed", False):
        raise exceptions.PermissionDenied(
            "This list mirrors a classifier's category map and is kept in sync automatically. "
            "Copy it to a new list to make changes."
        )


def check_processingservice_write_permission(user, processing_service) -> bool:
    """Thin alias kept so branches stacked on this one still import this name."""
    return check_public_scoped_write_permission(
        user, processing_service, lambda: bool(user.is_superuser or is_active_staff(user))
    )


def add_processingservice_permissions(user, instance, response_data: dict) -> dict:
    """
    Add update/delete to user_permissions for a ProcessingService.

    Unlike add_m2m_object_permissions, this skips the M2M membership check and
    the guardian lookup entirely: no per-project *_processingservice guardian
    permission exists anywhere in this codebase (see Project.Permissions and
    ami/users/roles.py), so that branch could only ever fire for a superuser,
    which a plain attribute check already covers for free. A public instance
    still checks the platform manage_public_processingservice permission.
    """
    perms = set(response_data.get("user_permissions", []))
    if getattr(instance, "is_public", False):
        if user_can_manage_public(user, instance):
            perms.update(["update", "delete"])
    elif user.is_superuser:
        perms.update(["update", "delete"])
    response_data["user_permissions"] = list(perms)
    return response_data


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
    model's manage_public_<model> permission, not project membership.

    This is a temporary approach for the M2M permission gap described in #1120.
    Once that issue is resolved, this should be replaced by a generic permission
    class (Pattern B: Bare M2M) that handles TaxaList, Taxon, ProcessingService,
    Pipeline, and other M2M-to-Project models uniformly.

    A managed instance (see TaxaList.is_managed) never advertises "delete": its
    membership belongs to an automatic sync, and the API refuses to delete it
    for anyone regardless of the permissions computed below.
    """
    perms = set(response_data.get("user_permissions", []))
    is_managed = getattr(instance, "is_managed", False)

    if getattr(instance, "is_public", False):
        if user_can_manage_public(user, instance):
            perms.update(["update", "delete"])
        if is_managed:
            perms.discard("delete")
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

    if is_managed:
        perms.discard("delete")
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


class _BaseGateOrPublicManager(permissions.BasePermission):
    """
    Shared shape for M2M-to-project models with a public flag: safe methods are
    open to everyone; unsafe methods need the model's own base gate (project
    membership, active-staff status, ...) or the manage_public_<model> platform
    permission. Actions named in `base_gate_only_actions` (creating a new row,
    copying into the active project) go through the base gate only, since the
    row being written does not exist yet to tell whether it will be public. Subclasses implement get_model() and
    get_base_gate() — get_model() does a local import to avoid a module-level
    circular import between this file and the app that owns the model.
    """

    base_gate_only_actions: frozenset[str] = frozenset()
    # Actions that only read the object (e.g. copying it) skip the object-level write check.
    read_only_object_actions: frozenset[str] = frozenset()

    def get_model(self):
        raise NotImplementedError

    def get_base_gate(self, request, view) -> bool:
        raise NotImplementedError

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:  # type: ignore[union-attr]
            return True

        if getattr(view, "action", None) in self.base_gate_only_actions:
            return self.get_base_gate(request, view)

        if user_can_manage_public(request.user, self.get_model()):
            return True

        return self.get_base_gate(request, view)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if getattr(view, "action", None) in self.read_only_object_actions:
            return True
        return check_public_scoped_write_permission(request.user, obj, lambda: self.get_base_gate(request, view))


class IsProjectMemberOrPublicListManager(_BaseGateOrPublicManager):
    """
    Used by the nested add/remove-taxon route: serves both public and
    project-scoped lists, and has no object to check yet at has_permission()
    time.
    """

    def get_model(self):
        from ami.main.models import TaxaList

        return TaxaList

    def get_base_gate(self, request, view):
        get_active_project = getattr(view, "get_active_project", None)
        project = get_active_project() if get_active_project else None
        return bool(project and project.members.filter(pk=request.user.pk).exists())


class IsProjectMemberOrPublicListManagerOrReadOnly(IsProjectMemberOrPublicListManager):
    """
    For TaxaListViewSet. Creating a list, or copying one into the active project, needs
    real project membership. `copy` only reads its source, which get_object() has already
    limited to lists the caller can see, so the write check does not apply to it.
    """

    base_gate_only_actions = frozenset({"create", "copy"})
    read_only_object_actions = frozenset({"copy"})

    def has_object_permission(self, request, view, obj):
        # A managed list refuses DELETE for everyone before the usual write check.
        if request.method == "DELETE":
            check_taxalist_not_managed(obj)
        return super().has_object_permission(request, view, obj)


class IsActiveStaffOrPublicManager(_BaseGateOrPublicManager):
    """Used by ProcessingServiceViewSet's non-create actions and any future nested route."""

    def get_model(self):
        from ami.ml.models.processing_service import ProcessingService

        return ProcessingService

    def get_base_gate(self, request, view):
        return is_active_staff(request.user)


class IsActiveStaffOrPublicManagerOrReadOnly(IsActiveStaffOrPublicManager):
    """For ProcessingServiceViewSet: creating a brand-new service always needs active-staff status."""

    base_gate_only_actions = frozenset({"create"})


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
