"""Work out which occurrences a tracking run merges, from links and the current grouping, without a database.

A run only adds: it links detections and merges the occurrences those links join, and it never
moves a detection away from the other detections of its occurrence. So the unit of change is a
group of detections connected by links (earlier ones and this run's) or by sharing an occurrence.
A link that would join occurrences whose human identifications name different taxa is not followed,
so a run never puts a machine's grouping above what people told apart.
"""

import dataclasses
from collections.abc import Mapping, Sequence, Set


@dataclasses.dataclass
class MergeGroup:
    """Detections a run puts in one occurrence, in capture order, and the occurrence each held before."""

    detection_ids: list[int]
    previous_occurrence_ids: list[int | None]
    # The occurrence the group keeps: the first identified one in capture order, else the first one, else
    # None to create one. Keeping the identified occurrence keeps the id people may have linked to.
    keeper_id: int | None
    # One entry per detection, in the order of ``detection_ids``: the cost of the link this run made from
    # it, or None when its link is older, was refused, or it is the last. See #1412 for the planned shape.
    link_costs: list[float | None]

    @property
    def absorbed_ids(self) -> list[int]:
        """Occurrences other than the keeper that held detections of the group, in id order."""
        return sorted({pk for pk in self.previous_occurrence_ids if pk is not None and pk != self.keeper_id})


@dataclasses.dataclass
class MergePlan:
    groups: list[MergeGroup]
    # The earlier detection of each link not followed because it would join occurrences whose
    # identifications disagree, in capture order. A refused link of this run is not saved.
    refused_links: list[int]


def merge_groups(
    detection_order: Sequence[int],
    occurrence_of: Mapping[int, int | None],
    links: Mapping[int, int],
    new_link_costs: Mapping[int, float],
    identified_taxa: Mapping[int, Set[int | None]] | None = None,
) -> MergePlan:
    """The groups whose grouping a run changes, in capture order of their first detection.

    ``detection_order`` lists the detections in capture order; ``occurrence_of`` gives each one's
    occurrence; ``links`` maps a detection to the next one, for earlier links and this run's;
    ``new_link_costs`` gives the cost of this run's links, keyed by the earlier detection;
    ``identified_taxa`` gives the taxa of each identified occurrence's active identifications. A group
    already held by one occurrence, with every detection in it, is left out because nothing changes.

    Links are followed in capture order. One is refused when both sides already hold identified
    occurrences and their taxa are not the same set, so an occurrence two people disagree on is not
    joined to one that names only one of their taxa.
    """
    identified_taxa = identified_taxa or {}
    parent = {pk: pk for pk in detection_order}
    # The identified taxa each group holds so far, keyed by the group's root.
    taxa_of: dict[int, frozenset[int | None]] = {}

    def find(pk: int) -> int:
        while parent[pk] != pk:
            parent[pk] = parent[parent[pk]]
            pk = parent[pk]
        return pk

    def union(a: int, b: int) -> bool:
        """Join the groups of ``a`` and ``b`` unless their identified taxa disagree; return whether they are one."""
        root_a, root_b = find(a), find(b)
        if root_a == root_b:
            return True
        taxa_a, taxa_b = taxa_of.get(root_a, frozenset()), taxa_of.get(root_b, frozenset())
        if taxa_a and taxa_b and taxa_a != taxa_b:
            return False
        parent[root_b] = root_a
        taxa_of[root_a] = taxa_a | taxa_b
        return True

    # Detections of one occurrence are always one group, whatever its identifications say.
    first_with_occurrence: dict[int, int] = {}
    for pk in detection_order:
        occurrence_id = occurrence_of.get(pk)
        if occurrence_id is None:
            continue
        if occurrence_id in first_with_occurrence:
            union(first_with_occurrence[occurrence_id], pk)
        else:
            first_with_occurrence[occurrence_id] = pk
            if identified_taxa.get(occurrence_id):
                taxa_of[pk] = frozenset(identified_taxa[occurrence_id])
    refused = [
        source
        for source in detection_order
        if source in links and links[source] in parent and not union(source, links[source])
    ]

    members: dict[int, list[int]] = {}
    for pk in detection_order:
        members.setdefault(find(pk), []).append(pk)

    refused_set = set(refused)
    groups = []
    for detection_ids in members.values():
        previous = [occurrence_of.get(pk) for pk in detection_ids]
        held_by = {pk for pk in previous if pk is not None}
        if len(held_by) == 1 and None not in previous:
            continue
        keeper_id = next(
            (pk for pk in previous if pk is not None and identified_taxa.get(pk)),
            next((pk for pk in previous if pk is not None), None),
        )
        costs = [
            round(new_link_costs[pk], 4) if pk in new_link_costs and pk not in refused_set else None
            for pk in detection_ids
        ]
        groups.append(MergeGroup(detection_ids, previous, keeper_id, costs))
    return MergePlan(groups, refused)
