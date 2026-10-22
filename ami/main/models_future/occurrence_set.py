"""
Occurrence sets: named groups of occurrences that a project keeps and uses again.

Models are declared here but remain in the ``main`` app. Related models are
referenced by string label, so this module never imports ``ami.main.models`` at
import time — ``main.models`` imports this one.
"""

import typing
from typing import final

from django.db import models

from ami.base.models import BaseModel, BaseQuerySet
from ami.base.sets.models import SavedSetMixin, SetRefused

if typing.TYPE_CHECKING:
    from ami.main.models import Project


class OccurrenceSetMethod(models.TextChoices):
    """How the members of an occurrence set are produced."""

    # By hand: flags, favourites, a script or a backend task.
    CURATED = "curated", "Manually curated"
    # Upcoming methods, see #1548:
    # FILTERS = "filters", "Populated from occurrence-list filters"
    # RANDOM = "random", "Random sample"
    # STRATIFIED = "stratified", "Balanced sample across stations, sites and times of night"
    # COPY = "copy", "Copy of another set"


class OccurrenceSetQuerySet(BaseQuerySet):
    def for_project(self, project: "Project") -> "OccurrenceSetQuerySet":
        """The sets that can be used in this project: its own."""
        return self.filter(project=project)

    def with_occurrences_count(self) -> "OccurrenceSetQuerySet":
        # distinct: visible_for_user() joins project members, which repeats each row.
        return self.annotate(occurrences_count=models.Count("occurrences", distinct=True))


class OccurrenceSetManager(models.Manager.from_queryset(OccurrenceSetQuerySet)):
    pass


@final
class OccurrenceSet(BaseModel, SavedSetMixin):
    """
    A named group of occurrences that a project keeps and uses again.

    A set can narrow the occurrence list, be exported, narrow the taxa list, be the data a
    model is scored on, and be included in or excluded from occurrence stats. It belongs to
    one project, as its occurrences do. Jobs and results refer to it by its ``reference_type``.

    For now every set is manually curated: people, scripts and jobs add and remove its
    occurrences. Sets populated from occurrence-list filters come next, then frozen sets
    and copies. See #1548.
    """

    reference_type = "occurrence_set"
    reference_name_field = "name"
    members_field = "occurrences"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    project = models.ForeignKey(
        "Project",  # String to avoid circular import with ami.main.models.
        on_delete=models.CASCADE,
        related_name="occurrence_sets",
    )
    method = models.CharField(
        max_length=255,
        choices=OccurrenceSetMethod.choices,
        default=OccurrenceSetMethod.CURATED,
        help_text="How the members are produced.",
    )
    # kwargs = models.JSONField(default=dict, blank=True)  # arrives with the filters method, see #1548
    occurrences = models.ManyToManyField(
        "Occurrence",
        through="OccurrenceSetMember",
        related_name="occurrence_sets",
        blank=True,
    )

    objects: OccurrenceSetManager = OccurrenceSetManager()

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        # Remember the stored project, so save() can refuse a change of project.
        instance._stored_project_id = instance.__dict__.get("project_id")
        return instance

    def save(self, *args, **kwargs):
        stored_project_id = getattr(self, "_stored_project_id", None)
        if stored_project_id is not None and stored_project_id != self.project_id:
            # The members belong to the stored project.
            raise SetRefused("The project of an occurrence set cannot change.")
        super().save(*args, **kwargs)
        self._stored_project_id = self.project_id

    def member_queryset(self, ids: typing.Collection[int]) -> models.QuerySet:
        from ami.main.models import Occurrence

        return Occurrence.objects.filter(project_id=self.project_id, pk__in=ids)

    def occurrences_count(self) -> int | None:
        # Annotated by OccurrenceSetQuerySet.with_occurrences_count()
        return None

    def check_custom_permission(self, user, action: str) -> bool:
        # Adding and removing occurrences is an edit of the set.
        action = {"add": "update", "remove": "update"}.get(action, action)
        return super().check_custom_permission(user, action)


@final
class OccurrenceSetMember(models.Model):
    """One occurrence in one occurrence set, and when it was added."""

    occurrence_set = models.ForeignKey(OccurrenceSet, on_delete=models.CASCADE, related_name="memberships")
    occurrence = models.ForeignKey(
        "Occurrence",
        on_delete=models.CASCADE,
        related_name="occurrence_set_memberships",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["occurrence_set", "occurrence"], name="unique_occurrence_set_member"),
        ]
