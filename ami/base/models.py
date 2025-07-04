from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.db import models
from guardian.shortcuts import get_perms

import ami.tasks


class BaseModel(models.Model):
    """ """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_project(self):
        """Get the project associated with the model."""
        return self.project if hasattr(self, "project") else None

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

    def check_permission(self, user: AbstractUser | AnonymousUser, action: str) -> bool:
        project = self.get_project() if hasattr(self, "get_project") else None
        if not project:
            return False
        if action == "retrieve":
            # Allow view
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
        """To be overridden in models for non-CRUD actions"""
        assert self._meta.model_name is not None, "Model must have a model_name defined in Meta class."
        model_name = self._meta.model_name.lower()
        permission_codename = f"{action}_{model_name}"
        project = self.get_project() if hasattr(self, "get_project") else None

        return user.has_perm(permission_codename, project)

    def get_user_object_permissions(self, user) -> list[str]:
        """
        Returns a list of object-level permissions the user has on this instance,
        based on their role in the associated project.
        """

        project = self.get_project()
        if not project:
            return []

        if user.is_superuser:
            custom_perms = self.get_custom_user_permissions(user)
            return ["update", "delete"] + custom_perms
        allowed_perms = set()
        model_name = self._meta.model_name
        perms = get_perms(user, project)
        # check for update and delete permissions
        actions = ["update", "delete"]
        for action in actions:
            if f"{action}_{model_name}" in perms:
                allowed_perms.add(action)
        custom_perms = self.get_custom_user_permissions(user)
        allowed_perms.update(set(custom_perms))
        return list(allowed_perms)

    def get_custom_user_permissions(self, user: AbstractUser | AnonymousUser) -> list[str]:
        project = self.get_project()
        if not project:
            return []

        custom_perms = set()
        model_name = self._meta.model_name
        perms = get_perms(user, project)
        for perm in perms:
            # permissions are in the format "action_modelname"
            if perm.endswith(f"_{model_name}"):
                # process_single_image_sourceimage
                action = perm.split("_", 1)[0]
                # make sure to exclude standard CRUD actions
                if action not in ["view", "create", "update", "delete"]:
                    custom_perms.add(action)
        return list(custom_perms)

    class Meta:
        abstract = True
