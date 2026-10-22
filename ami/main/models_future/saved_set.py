"""
Saved sets: the lifecycle that occurrence sets share, and that capture sets and taxa
lists can adopt later.

A saved set is a named group of records that people keep and use again. Every kind of
set keeps its own members and its own ``method`` and ``kwargs``. This module holds what
is the same for all of them: when the members were produced, the freeze, and the copy.
See the design notes on the "Save and reuse sets from list views" epic.
"""

import typing

from django.db import models, transaction
from django.utils import timezone

if typing.TYPE_CHECKING:
    from ami.users.models import User

SavedSetT = typing.TypeVar("SavedSetT", bound="SavedSetMixin")


class SetRefused(Exception):
    """The state of the set does not allow the action, for example editing a frozen set."""


class SavedSetMixin(models.Model):
    """
    The populate date, the freeze and the copy of a saved set.

    - ``populated_at`` says when the members were last produced from saved filters.
      Nothing sets it until sets get a ``filters`` method.
    - ``frozen_at`` and ``frozen_by`` record a freeze. A frozen set cannot change its
      members, so a score or an export that refers to it stays true. There is no
      unfreeze: copy the set instead.
    - ``copied_from`` is the set a copy was made from.

    The model also needs ``name`` and ``updated_at`` (from ``BaseModel``). It names the
    fields a copy keeps (``copy_fields``) and
    copies its members in ``copy_members_to()``. Methods that change the members call
    ``lock()`` and then ``refuse_if_frozen()`` in one transaction.
    """

    populated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the members were last produced from saved filters. Empty until sets can be populated.",
    )
    frozen_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When the set was frozen. The members of a frozen set cannot change.",
    )
    frozen_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="frozen_%(class)ss",
    )
    copied_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="copies",
    )

    # Fields that a copy keeps, besides the members. The copy gets a new name.
    copy_fields: typing.ClassVar[tuple[str, ...]] = ("description",)
    # Fields that lock() reads again, because actions check them before they write.
    state_fields: typing.ClassVar[tuple[str, ...]] = ("populated_at", "frozen_at", "frozen_by_id")

    class Meta:
        abstract = True

    @property
    def is_frozen(self) -> bool:
        return self.frozen_at is not None

    def lock(self):
        """Read the state of the set again and lock its row until the transaction ends.

        Actions check the state and then write, so two of them must not interleave, for
        example a freeze in the middle of an edit. Call it inside ``transaction.atomic()``.
        """
        locked = type(self).objects.select_for_update().get(pk=self.pk)
        for field in self.state_fields:
            setattr(self, field, getattr(locked, field))

    def refuse_if_frozen(self, action: str):
        if self.is_frozen:
            raise SetRefused(f"A frozen set cannot be {action}. Copy it to make a set that can change.")

    def freeze(self, user: "User | None"):
        """Freeze the set for good. Its members cannot change from then on."""
        with transaction.atomic():
            self.lock()
            self.refuse_if_frozen("frozen again")
            self.frozen_at = timezone.now()
            self.frozen_by = user
            self.save(update_fields=["frozen_at", "frozen_by", "updated_at"])

    def copy(self: SavedSetT, name: str | None = None) -> SavedSetT:
        """A new set with the same fields and members, not frozen, that records where it came from."""
        with transaction.atomic():
            self.lock()
            copy = type(self).objects.create(
                name=name or f"Copy of {self.name}"[:255],
                **{field: getattr(self, field) for field in self.copy_fields},
                # The members are as old as the ones they were copied from.
                populated_at=self.populated_at,
                copied_from=self,
            )
            self.copy_members_to(copy)
        return copy

    def copy_members_to(self, copy: SavedSetT):
        raise NotImplementedError
