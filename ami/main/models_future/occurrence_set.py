"""
Occurrence sets: named groups of occurrences that a project keeps and uses again.

Models are declared here but remain in the ``main`` app. Related models are
referenced by string label, or imported inside the method that needs them, so
this module never imports ``ami.main.models`` at import time — ``main.models``
imports this one.
"""

import typing
from typing import final

from django.db import connection, models, transaction

from ami.base.models import BaseModel, BaseQuerySet
from ami.main.models_future.saved_set import SavedSetMixin


class OccurrenceSetMethod(models.TextChoices):
    """How the members of an occurrence set are produced."""

    # By hand: flags, favourites, a script or a backend task.
    MANUAL = "manual", "Manual"


class OccurrenceSetQuerySet(BaseQuerySet):
    def with_occurrences_count(self) -> "OccurrenceSetQuerySet":
        # distinct: visible_for_user() joins project members, which repeats each row.
        return self.annotate(occurrences_count=models.Count("occurrences", distinct=True))


class OccurrenceSetManager(models.Manager.from_queryset(OccurrenceSetQuerySet)):
    pass


@final
class OccurrenceSet(SavedSetMixin, BaseModel):
    """
    A named group of occurrences that a project keeps and uses again.

    People and jobs use a set to review its occurrences in the occurrence list, to
    export them, to see which taxa they contain, to score a classifier against their
    human identifications, and to include or exclude them in occurrence stats
    (``occurrence_set_id`` and ``not_occurrence_set_id``). A set belongs to one
    project, as its occurrences do. Jobs and results refer to a set by its
    ``reference_type``.

    Every set is described by the same properties, not by a type:

    - ``method`` says how the members are produced, and ``kwargs`` holds its
      arguments, as for capture sets. Today the only method is ``manual``: people,
      scripts and jobs add and remove members by hand, and ``kwargs`` is empty.
    - ``occurrences`` holds the stored members. Every use reads them; there is no
      live mode.
    - The freeze, the copy and ``populated_at`` come from ``SavedSetMixin``. A frozen
      set cannot change its members; to change it, copy it.

    Next, a ``filters`` method will produce the members from occurrence-list filters
    saved in ``kwargs``: populate (in a job, setting ``populated_at``), compare (what
    populating again would change) and convert to manual. Samplers will follow.
    """

    reference_type = "occurrence_set"
    reference_name_field = "name"

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
        default=OccurrenceSetMethod.MANUAL,
        help_text="How the members are produced. Only by hand (manual) for now.",
    )
    kwargs = models.JSONField(
        "Arguments",
        blank=True,
        default=dict,
        help_text="Arguments for the method (JSON object). Empty for a manual set.",
    )
    occurrences = models.ManyToManyField("Occurrence", related_name="occurrence_sets", blank=True)

    copy_fields = ("project_id", "description", "method", "kwargs")
    state_fields = SavedSetMixin.state_fields + ("method", "kwargs")

    objects: OccurrenceSetManager = OccurrenceSetManager()

    def occurrences_count(self) -> int | None:
        # Annotated by OccurrenceSetQuerySet.with_occurrences_count()
        return None

    def check_custom_permission(self, user, action: str) -> bool:
        # Hand edits and freezing are edits of the set. A copy is a new set.
        action = {"add": "update", "remove": "update", "freeze": "update", "copy": "create"}.get(action, action)
        return super().check_custom_permission(user, action)

    def check_editable_by_hand(self):
        """Raise ``SetRefused`` (from ``saved_set``) unless members can be added or removed by hand."""
        self.refuse_if_frozen("edited")

    def add_occurrences(self, occurrence_ids: typing.Iterable[int]):
        """Add members by hand. The caller checks that the occurrences belong to the project."""
        with transaction.atomic():
            self._start_hand_edit()
            self.occurrences.add(*occurrence_ids)

    def remove_occurrences(self, occurrence_ids: typing.Iterable[int]):
        """Remove members by hand. Occurrences that are not members are ignored."""
        with transaction.atomic():
            self._start_hand_edit()
            self.occurrences.remove(*occurrence_ids)

    def _start_hand_edit(self):
        self.lock()
        self.check_editable_by_hand()
        self.save(update_fields=["updated_at"])

    def copy_members_to(self, copy: "OccurrenceSet"):
        """Copy the members in one statement, so a set of any size is never loaded into Python."""
        membership = OccurrenceSet.occurrences.through
        quote = connection.ops.quote_name
        set_column = quote(membership._meta.get_field("occurrenceset").column)
        occurrence_column = quote(membership._meta.get_field("occurrence").column)
        table = quote(membership._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {table} ({set_column}, {occurrence_column}) "
                f"SELECT %s, {occurrence_column} FROM {table} WHERE {set_column} = %s",
                [copy.pk, self.pk],
            )
