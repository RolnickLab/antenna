"""
Saved sets: named groups of records that a project keeps and uses again.

Occurrence sets use this first. Capture sets and taxa lists will adopt it. See #1548.

Rule: nothing in ``ami.base.sets`` imports from ``ami.main``. Each set model lives next
to its members and defines what is specific to it: its members field, which records may
join, its ``method`` choices, and how it is populated.
"""

import typing

from django.db import models


class SetRefused(Exception):
    """The set cannot do what was asked, for example add a record from another project."""


class SavedSetMixin(models.Model):
    """
    Membership of a saved set: add, remove and count members, in bulk.

    A set model names its many-to-many field in ``members_field`` and returns the records
    that may join in ``member_queryset()``. Each set model also defines ``method``, which
    says how its members are produced.

    A shared lifecycle comes next (#1548). ``populated_at`` will record when the members
    were last produced from saved filters. A freeze (``frozen_at``, ``frozen_by``) will
    stop all member changes, so a score or an export that refers to the set stays true.
    A copy will make a new set that can change, and record ``copied_from``.
    """

    # populated_at = models.DateTimeField(null=True, blank=True)  # See #1548
    # frozen_at = models.DateTimeField(null=True, blank=True, db_index=True)  # See #1548
    # frozen_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL)  # See #1548
    # copied_from = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)  # See #1548

    # The name of the many-to-many field that holds the members.
    members_field: typing.ClassVar[str]

    class Meta:
        abstract = True

    def member_queryset(self, ids: typing.Collection[int]) -> models.QuerySet:
        """The records among ``ids`` that may be members of this set."""
        raise NotImplementedError

    def _membership(self) -> tuple[type[models.Model], str, str]:
        """The through model, and the names of its columns for this set and for the member."""
        field = self._meta.get_field(self.members_field)
        through = field.remote_field.through
        set_column = through._meta.get_field(field.m2m_field_name()).attname
        member_column = through._meta.get_field(field.m2m_reverse_field_name()).attname
        return through, set_column, member_column

    def add_members(self, ids: typing.Iterable[int]) -> int:
        """Add records by id, and return how many were not members before.

        All or nothing: if any id is not in ``member_queryset()``, nothing is added and
        ``SetRefused`` names those ids. Records that are already members stay as they are.
        """
        ids = set(ids)
        if not ids:
            return 0
        allowed = set(self.member_queryset(ids).order_by().values_list("pk", flat=True))
        refused = sorted(ids - allowed)
        if refused:
            raise SetRefused(f"These records cannot be added to this set: {refused}")
        through, set_column, member_column = self._membership()
        existing = set(
            through.objects.filter(**{set_column: self.pk, f"{member_column}__in": ids}).values_list(
                member_column, flat=True
            )
        )
        new_ids = ids - existing
        through.objects.bulk_create(
            [through(**{set_column: self.pk, member_column: member_id}) for member_id in new_ids],
            ignore_conflicts=True,
        )
        return len(new_ids)

    def remove_members(self, ids: typing.Iterable[int]) -> int:
        """Remove records by id, and return how many were removed. Ids that are not members are ignored."""
        through, set_column, member_column = self._membership()
        deleted, _ = through.objects.filter(**{set_column: self.pk, f"{member_column}__in": set(ids)}).delete()
        return deleted

    def member_count(self) -> int:
        through, set_column, _ = self._membership()
        return through.objects.filter(**{set_column: self.pk}).count()
