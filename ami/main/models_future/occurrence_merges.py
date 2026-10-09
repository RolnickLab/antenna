"""Merging occurrences: fold whole occurrences into others so no row that pointed at them is lost.

Every merge path calls ``merge_occurrences``; tracking is the first. Each table that links to an
occurrence has a rule in ``MERGE_RULES``, and a test fails when a new link has none, because a link
with ``on_delete=CASCADE`` would otherwise lose its rows when the absorbed occurrence is deleted.
"""

import collections
import dataclasses
import enum
from collections.abc import Iterable, Mapping

from cachalot.api import cachalot_disabled
from django.apps import apps
from django.db import connection, models, transaction

from ami.main.models import Identification, Occurrence, update_occurrence_determination

# Rows per statement when occurrence determinations are written in bulk.
WRITE_BATCH_SIZE = 1000


class MergeRule(enum.Enum):
    # Point the rows at the kept occurrence.
    MOVE = "move"
    # Move, then leave each user one active identification per occurrence, as saving one does.
    MOVE_AND_WITHDRAW_DUPLICATES = "move_and_withdraw_duplicates"


# Every link to an occurrence, as (model label, field name): what a merge does with its rows, and the
# field of ``OccurrenceMerge`` that records them.
MERGE_RULES: dict[tuple[str, str], tuple[MergeRule, str]] = {
    ("main.Detection", "occurrence"): (MergeRule.MOVE, "moved_detections"),
    ("main.Identification", "occurrence"): (MergeRule.MOVE_AND_WITHDRAW_DUPLICATES, "moved_identifications"),
    # Results are only ever added, so two results of one algorithm on the kept occurrence are both history.
    ("ml.AlgorithmResult", "occurrence"): (MergeRule.MOVE, "moved_results"),
}


@dataclasses.dataclass
class OccurrenceMerge:
    """What a merge moved, keyed by kept occurrence, so the earlier grouping can be put back."""

    absorbed: dict[int, list[int]] = dataclasses.field(default_factory=dict)
    # (row id, the occurrence it was in) for each row moved.
    moved_detections: dict[int, list[tuple[int, int]]] = dataclasses.field(default_factory=dict)
    moved_identifications: dict[int, list[tuple[int, int]]] = dataclasses.field(default_factory=dict)
    moved_results: dict[int, list[tuple[int, int]]] = dataclasses.field(default_factory=dict)
    withdrawn_identification_ids: dict[int, list[int]] = dataclasses.field(default_factory=dict)


def merge_occurrences(absorbed_into: Mapping[int, int], *, recompute_determinations: bool = True) -> OccurrenceMerge:
    """Fold each absorbed occurrence into the occurrence it maps to, ``{absorbed id: kept id}``, then delete it.

    Refuses, writing nothing, a merge across projects or sessions, a chain (an occurrence both kept and
    absorbed) and ids that do not exist. Runs in its own transaction, or a savepoint of the caller's, and
    locks the occurrences in id order. Each table takes a fixed number of statements however many
    occurrences merge. Session and station counts are left to the caller, since refreshing them scans
    whole stations. Pass ``recompute_determinations=False`` to refresh determinations yourself with
    ``refresh_determinations``.
    """
    merge = OccurrenceMerge()
    if not absorbed_into:
        return merge
    absorbed_into = dict(absorbed_into)
    both = set(absorbed_into) & set(absorbed_into.values())
    if both:
        raise ValueError(f"Occurrences {sorted(both)} are both kept and absorbed in one merge.")
    for absorbed_id, kept_id in sorted(absorbed_into.items()):
        merge.absorbed.setdefault(kept_id, []).append(absorbed_id)

    with transaction.atomic():
        _lock_and_check(absorbed_into)
        for (label, field_name), (rule, record_field) in MERGE_RULES.items():
            moved = _repoint(apps.get_model(label), field_name, absorbed_into)
            setattr(merge, record_field, moved)
            if rule is MergeRule.MOVE_AND_WITHDRAW_DUPLICATES and moved:
                merge.withdrawn_identification_ids = withdraw_duplicate_identifications(set(moved))
        Occurrence.objects.filter(pk__in=sorted(absorbed_into)).delete()
        if recompute_determinations:
            refresh_determinations(
                Occurrence.objects.select_related("determination").filter(pk__in=sorted(merge.absorbed))
            )
    return merge


def _lock_and_check(absorbed_into: dict[int, int]) -> None:
    ids = sorted(set(absorbed_into) | set(absorbed_into.values()))
    rows = {
        pk: (project_id, event_id)
        for pk, project_id, event_id in Occurrence.objects.select_for_update()
        .filter(pk__in=ids)
        .order_by("pk")
        .values_list("pk", "project_id", "event_id")
    }
    missing = sorted(set(ids) - set(rows))
    if missing:
        raise ValueError(f"Cannot merge occurrences that do not exist: {missing}.")
    # An unknown project or session (null) is not treated as a different one.
    if len({project_id for project_id, _ in rows.values() if project_id is not None}) > 1:
        raise ValueError("Cannot merge occurrences into an occurrence of another project.")
    for absorbed_id, kept_id in absorbed_into.items():
        absorbed_event, kept_event = rows[absorbed_id][1], rows[kept_id][1]
        if absorbed_event is not None and kept_event is not None and absorbed_event != kept_event:
            raise ValueError(
                f"Cannot merge Occurrence #{absorbed_id} into Occurrence #{kept_id}, which is in another session."
            )


def _repoint(
    model: type[models.Model], field_name: str, absorbed_into: dict[int, int]
) -> dict[int, list[tuple[int, int]]]:
    """Point the rows of ``model`` linked to an absorbed occurrence at its kept one, in one statement.

    Returns ``{kept id: [(row id, earlier occurrence id), ...]}``, in row order.
    """
    column = model._meta.get_field(field_name).column
    rows = list(
        model.objects.filter(**{f"{column}__in": list(absorbed_into)}).order_by("pk").values_list("pk", column)
    )
    moved: dict[int, list[tuple[int, int]]] = collections.defaultdict(list)
    for pk, occurrence_id in rows:
        moved[absorbed_into[occurrence_id]].append((pk, occurrence_id))
    if rows:
        quote = connection.ops.quote_name
        with connection.cursor() as cursor:
            # An unnest join rather than a CASE per occurrence, so the statement stays small for big merges.
            cursor.execute(
                f"UPDATE {quote(model._meta.db_table)} AS t SET {quote(column)} = v.kept "
                f"FROM unnest(%s::bigint[], %s::bigint[]) AS v(absorbed, kept) WHERE t.{quote(column)} = v.absorbed",
                [list(absorbed_into), list(absorbed_into.values())],
            )
    return dict(moved)


def withdraw_duplicate_identifications(occurrence_ids: set[int]) -> dict[int, list[int]]:
    """Leave each user one active identification per occurrence, the newest, as saving an identification does.

    Identifications moved by a merge skip ``Identification.save``, so a user who identified two of the
    merged occurrences would otherwise hold two active identifications on the one that is kept.
    Returns the ids withdrawn, by occurrence.
    """
    seen: set[tuple[int, int]] = set()
    withdrawn: dict[int, list[int]] = collections.defaultdict(list)
    for pk, occurrence_id, user_id in (
        Identification.objects.filter(occurrence_id__in=occurrence_ids, withdrawn=False, user__isnull=False)
        .order_by("occurrence_id", "user_id", "-created_at", "-pk")
        .values_list("pk", "occurrence_id", "user_id")
    ):
        if (occurrence_id, user_id) in seen:
            withdrawn[occurrence_id].append(pk)
        else:
            seen.add((occurrence_id, user_id))
    if withdrawn:
        Identification.objects.filter(pk__in=[pk for ids in withdrawn.values() for pk in ids]).update(withdrawn=True)
    return dict(withdrawn)


def refresh_determinations(occurrences: Iterable[Occurrence]) -> list[Occurrence]:
    """Recompute the determination of each occurrence and save those that changed in bulk.

    Load the occurrences with ``select_related("determination")``. Returns the occurrences that changed.
    """
    # The caller is changing these tables, so caching the reads only costs a cache key per query; writes
    # still invalidate the cache. Entered by hand because the context manager does not restore on error.
    uncached = cachalot_disabled()
    uncached.__enter__()
    try:
        changed = [
            occurrence
            for occurrence in occurrences
            if update_occurrence_determination(occurrence, current_determination=occurrence.determination, save=False)
        ]
    finally:
        uncached.__exit__(None, None, None)
    Occurrence.objects.bulk_update(changed, ["determination", "determination_score"], batch_size=WRITE_BATCH_SIZE)
    return changed
