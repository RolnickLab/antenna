"""
Occurrence sets: named groups of occurrences that projects keep and use again.

The model is declared here but stays in the ``main`` app. Related models are referenced by
string label so this module never imports ``ami.main.models`` at import time, since
``main.models`` imports this one. See #763.
"""

from typing import TYPE_CHECKING, final

from django.contrib.auth.models import AnonymousUser
from django.db import models

from ami.base.models import BaseModel, BaseQuerySet
from ami.users.models import User

if TYPE_CHECKING:
    from ami.main.models import Project


class OccurrenceSetQuerySet(BaseQuerySet):
    def for_project(self, project: "Project") -> "OccurrenceSetQuerySet":
        """Return the sets a project can use: its own sets and the public sets."""
        return self.filter(models.Q(projects=project) | models.Q(projects__isnull=True)).distinct()

    def visible_for_user(self, user: User | AnonymousUser) -> "OccurrenceSetQuerySet":
        """
        Return the sets this user may see.

        A project set is visible when its project is visible to the user. A public set has
        no project and is visible to everyone. The base queryset keeps only rows linked to a
        visible project, so it would hide every public set; this adds them back. See #1424.
        """
        visible = super().visible_for_user(user)
        return self.filter(models.Q(pk__in=visible.values("pk")) | models.Q(projects__isnull=True)).distinct()

    def with_occurrences_count(self) -> "OccurrenceSetQuerySet":
        # Count distinct occurrences: the filters for public sets join the projects table,
        # which repeats each row once for each project of the set.
        return self.annotate(occurrences_count=models.Count("occurrences", distinct=True))


@final
class OccurrenceSet(BaseModel):
    """
    A named group of occurrences that a project keeps and uses again.

    A set can narrow the occurrence list, scope an export, or be the data a classifier is
    scored or trained on. Its members are stored, one row per occurrence, so a set can be
    used later without repeating the work of choosing them. See #763 for the kinds of set
    that are planned, such as sets people edit by hand and sets made from saved filters.

    A set belongs to one or more projects. A set with no project is public and every
    project can use it, as with taxa lists. Only the Django admin makes public sets.
    """

    reference_type = "occurrence_set"
    reference_name_field = "name"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    occurrences = models.ManyToManyField("main.Occurrence", related_name="occurrence_sets", blank=True)
    projects = models.ManyToManyField(
        "main.Project",
        related_name="occurrence_sets",
        blank=True,
        help_text="Projects that use this set. A set with no project is public and every project can use it.",
    )

    objects = OccurrenceSetQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    @property
    def is_public(self) -> bool:
        return not self.projects.exists()

    def get_project(self) -> "Project | None":
        """
        Return the project whose permissions apply to this set, or None for a public set.

        A set shared by several projects uses the one that was created first. Without a
        project, ``BaseModel.check_permission`` refuses every action, so the API cannot
        change a public set. ``OccurrenceSetPermission`` still lets anyone read one, and
        checks an edit against the request's project when the set belongs to it.
        """
        return self.projects.order_by("pk").first()
