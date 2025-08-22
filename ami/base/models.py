from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.db import models
from django.db.models import Q, QuerySet
from guardian.shortcuts import get_perms

import ami.tasks


class BaseQuerySet(QuerySet):
    def visible_draft_projects_only(self, user):
        """
        Filter queryset to include only objects whose related draft projects
        are visible to the given user. Only superusers, project owners,
        or members are allowed to view draft projects and their related objects.
        """
        from ami.main.models import Project

        if user.is_superuser:
            return self

        # Determine whether the model is Project itself
        is_project_model = self.model == Project

        # Use model-defined project accessor if available
        project_accessor = getattr(self.model, "project_accessor", "project")
        project_field = "" if is_project_model else f"{project_accessor}__"

        # Build Q filters
        non_draft_filter = Q(**{f"{project_field}draft": False})
        # Show only non-draft projects for anonymous users
        if isinstance(user, AnonymousUser):
            return self.filter(non_draft_filter).distinct()

        owner_filter = Q(**{f"{project_field}owner": user})
        member_filter = Q(**{f"{project_field}members": user})

        return self.filter(non_draft_filter | owner_filter | member_filter).distinct()


class BaseModel(models.Model):
    """ """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = BaseQuerySet.as_manager()

    @classmethod
    def get_project_accessor(cls):
        return getattr(cls, "project_accessor", "project")

    def get_project(self):
        """Dynamically get the related project using the project_accessor."""
        accessor = self.get_project_accessor()
        if not accessor:
            return self
        project = self
        for part in accessor.split("__"):
            project = getattr(project, part, None)
            if project is None:
                break
        return project

    def __str__(self) -> str:
        """All django models should have this method."""
        if hasattr(self, "name"):
            name = getattr(self, "name") or "Untitled"
            return f"#{self.pk} {name}"
        else:
            return f"{self.__class__.__name__} #{self.pk}"

    def save_async(self, *args, **kwargs):
        """Save the model in a background task."""
        ami.tasks.model_task.delay(self.__class__.__name__, self.pk, "save", *args, **kwargs)

    def update_calculated_fields(self, *args, **kwargs):
        """Update calculated fields specific to each model."""
        pass

    def _get_object_perms(self, user):
        """
        Get the object-level permissions for the user on this instance.
        This method retrieves permissions like `update_modelname`, `create_modelname`, etc.
        """
        project = self.get_project()
        if not project:
            return []

        model_name = self._meta.model_name
        all_perms = get_perms(user, project)
        object_perms = [perm for perm in all_perms if perm.endswith(f"_{model_name}")]
        return object_perms

    def check_permission(self, user: AbstractUser | AnonymousUser, action: str) -> bool:
        """
        Check if the user has permission to perform the action
        on this instance.
        This method is used to determine if the user can perform
        CRUD operations or custom actions on the model instance.
        """
        from ami.users.roles import BasicMember

        project = self.get_project() if hasattr(self, "get_project") else None
        if not project:
            return False
        if action == "retrieve":
            if project.draft:
                # Allow view permission for members and owners of draft projects
                return BasicMember.has_role(user, project) or user == project.owner or user.is_superuser
            return True
        model = self._meta.model_name
        crud_map = {
            "create": f"create_{model}",
            "update": f"update_{model}",
            "partial_update": f"update_{model}",
            "destroy": f"delete_{model}",
        }

        if action in crud_map:
            return user.has_perm(crud_map[action], project)

        # Delegate to model-specific logic
        return self.check_custom_permission(user, action)

    def check_custom_permission(self, user: AbstractUser | AnonymousUser, action: str) -> bool:
        """Check custom permissions for the user on this instance.
        This is used for actions that are not standard CRUD operations.
        """
        assert self._meta.model_name is not None, "Model must have a model_name defined in Meta class."
        model_name = self._meta.model_name.lower()
        permission_codename = f"{action}_{model_name}"
        project = self.get_project() if hasattr(self, "get_project") else None

        return user.has_perm(permission_codename, project)

    def get_user_object_permissions(self, user) -> list[str]:
        """
        Returns a list of object-level permissions the user has on this instance.
        This is used by frontend to determine what actions the user can perform.
        """
        # Return all permissions for superusers
        if user.is_superuser:
            allowed_custom_actions = self.get_custom_user_permissions(user)
            return ["update", "delete"] + allowed_custom_actions

        object_perms = self._get_object_perms(user)
        # Check for update and delete permissions
        allowed_actions = set()
        for perm in object_perms:
            action = perm.split("_", 1)[0]
            if action in {"update", "delete"}:
                allowed_actions.add(action)

        allowed_custom_actions = self.get_custom_user_permissions(user)
        allowed_actions.update(set(allowed_custom_actions))
        return list(allowed_actions)

    def get_custom_user_permissions(self, user: AbstractUser | AnonymousUser) -> list[str]:
        """
        Returns a list of custom permissions (not standard CRUD actions) that the user has on this instance.
        """
        object_perms = self._get_object_perms(user)
        custom_perms = set()
        # Extract custom permissions that are not standard CRUD actions
        for perm in object_perms:
            action = perm.split("_", 1)[0]
            # Make sure to exclude standard CRUD actions
            if action not in ["view", "create", "update", "delete"]:
                custom_perms.add(action)
        return list(custom_perms)

    class Meta:
        abstract = True
