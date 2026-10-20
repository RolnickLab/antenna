"""
Occurrence sets: a named, fixed list of occurrences, and its queryset.

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
        """Sets this project can use: its own, plus public sets that belong to no project."""
        return self.filter(models.Q(projects=project) | models.Q(projects__isnull=True)).distinct()

    def visible_for_user(self, user: User | AnonymousUser) -> "OccurrenceSetQuerySet":
        """
        Project sets follow their project's visibility; public sets are visible to everyone.

        The inherited filter keeps a row only if it reaches a project the user may see, which
        a set with no project never does, so without this a public set would be hidden from
        everyone except superusers.
        """
        visible = super().visible_for_user(user)
        return self.filter(models.Q(pk__in=visible.values("pk")) | models.Q(projects__isnull=True)).distinct()

    def with_occurrences_count(self) -> "OccurrenceSetQuerySet":
        # distinct=True because visible_for_user() joins through projects, which repeats each
        # membership row once per project the set belongs to.
        return self.annotate(occurrences_count=models.Count("occurrences", distinct=True))


@final
class OccurrenceSet(BaseModel):
    """
    A named, fixed list of occurrences, kept so the same ones can be used again later.

    Membership is stored rather than described by a filter, because a filter answers
    differently as data arrives. Anything that compares results over time, such as scoring
    two classifiers, is only meaningful if both saw the same occurrences.

    Occurrences are chosen when a set is created; neither the API nor the Django admin adds
    any afterwards. Deleting or merging an occurrence does remove it from every set, through
    the many-to-many cascade (for example the ``cleanup_null_only_occurrences`` command, or
    merging tracks). What to do about that is left to a follow-up ticket under #763.

    A set with no projects is public and can be used by every project, following how
    ``TaxaList`` treats a list with no project. Public sets are created in the Django admin.
    Deleting a project deletes the sets that belonged only to it, so they never become public
    (see ``ami.main.signals``).
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    occurrences = models.ManyToManyField("main.Occurrence", related_name="occurrence_sets", blank=True)
    projects = models.ManyToManyField(
        "main.Project",
        related_name="occurrence_sets",
        blank=True,
        help_text="Projects this set belongs to. A set with none is available everywhere.",
    )

    objects = OccurrenceSetQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    @property
    def is_public(self) -> bool:
        return not self.projects.exists()

    def get_project(self) -> "Project | None":
        """
        The first of the set's projects governs its permissions; None for a public set.

        ``BaseModel.check_permission`` refuses every action without a project, including
        retrieve, so a public set cannot be read in detail or changed through the API.
        """
        return self.projects.first()
