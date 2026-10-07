"""Work out which occurrences a tracking run merges, from links and the current grouping, without a database.

A run only adds: it links detections and merges the occurrences those links join, and it never
moves a detection away from the other detections of its occurrence. So the unit of change is a
group of detections connected by links (earlier ones and this run's) or by sharing an occurrence.
"""

import dataclasses
from collections.abc import Mapping, Sequence


@dataclasses.dataclass
class MergeGroup:
    """Detections a run puts in one occurrence, in capture order, and the occurrence each held before."""

    detection_ids: list[int]
    previous_occurrence_ids: list[int | None]
    # The occurrence the group keeps: the first one held by a detection in capture order, or None to create one.
    keeper_id: int | None
    # The cost of each link this run made inside the group, in capture order of the earlier detection.
    link_costs: list[float]

    @property
    def absorbed_ids(self) -> list[int]:
        """Occurrences other than the keeper that held detections of the group, in id order."""
        return sorted({pk for pk in self.previous_occurrence_ids if pk is not None and pk != self.keeper_id})


def merge_groups(
    detection_order: Sequence[int],
    occurrence_of: Mapping[int, int | None],
    links: Mapping[int, int],
    new_link_costs: Mapping[int, float],
) -> list[MergeGroup]:
    """The groups whose grouping a run changes, in capture order of their first detection.

    ``detection_order`` lists the detections in capture order; ``occurrence_of`` gives each one's
    occurrence; ``links`` maps a detection to the next one, for earlier links and this run's;
    ``new_link_costs`` gives the cost of this run's links, keyed by the earlier detection. A group
    already held by one occurrence, with every detection in it, is left out because nothing changes.
    """
    parent = {pk: pk for pk in detection_order}

    def find(pk: int) -> int:
        while parent[pk] != pk:
            parent[pk] = parent[parent[pk]]
            pk = parent[pk]
        return pk

    def union(a: int, b: int) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    for source, target in links.items():
        if source in parent and target in parent:
            union(source, target)
    first_with_occurrence: dict[int, int] = {}
    for pk in detection_order:
        occurrence_id = occurrence_of.get(pk)
        if occurrence_id is None:
            continue
        if occurrence_id in first_with_occurrence:
            union(first_with_occurrence[occurrence_id], pk)
        else:
            first_with_occurrence[occurrence_id] = pk

    members: dict[int, list[int]] = {}
    for pk in detection_order:
        members.setdefault(find(pk), []).append(pk)

    groups = []
    for detection_ids in members.values():
        previous = [occurrence_of.get(pk) for pk in detection_ids]
        held_by = {pk for pk in previous if pk is not None}
        if len(held_by) == 1 and None not in previous:
            continue
        keeper_id = next((pk for pk in previous if pk is not None), None)
        costs = [round(new_link_costs[pk], 4) for pk in detection_ids if pk in new_link_costs]
        groups.append(MergeGroup(detection_ids, previous, keeper_id, costs))
    return groups
