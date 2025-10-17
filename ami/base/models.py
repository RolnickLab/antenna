from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.db import models
from django.db.models import Q, QuerySet
from guardian.shortcuts import get_perms

import ami.tasks
from ami.users.models import User


def has_one_to_many_project_relation(model: type[models.Model]) -> bool:
    """
    Returns True if the model has any ForeignKey or OneToOneField relationship to Project.
    """
    from ami.main.models import Project

    for field in model._meta.get_fields():
        if isinstance(field, (models.ForeignKey, models.OneToOneField)) and field.related_model == Project:
            return True

    return False


def has_many_to_many_project_relation(model: type[models.Model]) -> bool:
    """
    Returns True if the model has any forward or reverse ManyToMany relationship to Project.
    """
    from ami.main.models import Project

    # Forward M2M
    for field in model._meta.get_fields():
        if isinstance(field, models.ManyToManyField) and field.related_model == Project:
            return True

    # Reverse M2M
    for rel in Project._meta.related_objects:  # type: ignore
        if rel.related_model == model and rel.many_to_many:
            return True

    return False


class BaseQuerySet(QuerySet):
    def visible_for_user(self, user: User | AnonymousUser) -> QuerySet:
        """
        Filter queryset to include only objects whose related draft projects
        are visible to the given user. Only superusers, project owners,
        or members are allowed to view draft projects and their related objects.
        """
        from ami.main.models import Project

        # Superusers can see everything
        if user.is_superuser:
            return self

        # Anonymous users can only see non-draft projects/objects
        is_anonymous = isinstance(user, AnonymousUser)

        model = self.model

        # Handle Project model directly
        if model == Project:
            # Create a base filter condition for non-draft projects
            filter_condition = Q(draft=False)

            # If user is logged in, also include projects they own or are members of
            if not is_anonymous:
                filter_condition |= Q(owner=user) | Q(members=user)

            return self.filter(filter_condition).distinct()

        # For models related to Project
        project_accessor = model.get_project_accessor()

        # No project relationship: return unfiltered
        if project_accessor is None:
            return self

        # Get project field path with trailing double underscore
        project_field = f"{project_accessor}__"

        # Create a base filter condition for objects related to non-draft projects
        filter_condition = Q(**{f"{project_field}draft": False})

        # If user is logged in, also include objects related to projects they own or are members of
        if not is_anonymous:
            filter_condition |= Q(**{f"{project_field}owner": user}) | Q(**{f"{project_field}members": user})

        return self.filter(filter_condition).distinct()


class BaseModel(models.Model):
    """ """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = BaseQuerySet.as_manager()

    @classmethod
    def get_project_accessor(cls) -> str | None:
        """
        Determines the path to access the related Project from this model.

        This method returns the appropriate accessor path based on the model's relationship to Project:

        1. For direct ForeignKey or OneToOneField relationships to Project (occurrence.project)
            - Returns "project" automatically (no need to define project_accessor)

        2. For ManyToMany relationships to Project (pipeline.projects)
            - Returns "projects" automatically (no need to define project_accessor)
            - Note: Draft filtering will return objects with at least one non-draft project
            - This is appropriate for global objects (pipelines, taxa, etc.) that can belong to multiple projects
            - Such objects are never private data, unlike project-specific objects (occurrences, source_images)

        3. For indirect relationships (accessed through other models) (detection.occurrence.project):
            - Requires explicitly defining a 'project_accessor' class attribute
            - Uses the Django double underscore convention ("__") to navigate through relationships
            - Example: "deployment__project" (not "deployment.project")
                where "deployment" is a field on this model and "project" is a field on Deployment

        4. For the Project model itself:
            - No project_accessor needed; will be handled by the isinstance check in get_project()

        Returns:
            str|None: The path to the related project, or None for no relationship or the Project model itself.
        """

        if has_one_to_many_project_relation(cls):
            return "project"  # One-to-many or one-to-one relation

        if has_many_to_many_project_relation(cls):
            return "projects"  # Many-to-many relation

        return getattr(cls, "project_accessor", None)

    def get_project(self):
        """Dynamically get the related project using the project_accessor."""
        from ami.main.models import Project

        if isinstance(self, Project):
            return self

        accessor = self.get_project_accessor()
        if accessor == "projects" or accessor is None:
            return None

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

        model = self._meta.model_name
        crud_map = {
            "create": f"create_{model}",
            "update": f"update_{model}",
            "partial_update": f"update_{model}",
            "destroy": f"delete_{model}",
        }
        project = self.get_project() if hasattr(self, "get_project") else None
        # Check if the related project exists
        if not project.pk:
            return user.has_perm(f"main.{crud_map[action]}")

        if action == "retrieve":
            if project.draft:
                # Allow view permission for members and owners of draft projects
                return BasicMember.has_role(user, project) or user == project.owner or user.is_superuser
            return True

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
