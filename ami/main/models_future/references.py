"""Ids the occurrence history shows, resolved to ``{type, id, name}`` so the UI can link them with one table.

``name`` is None when the row no longer exists; the UI then shows the id as text. Resolution reads names
only, one query per type, and is used for ids stored on the occurrence's own results and jobs.
"""

import collections
import dataclasses
import typing

from django.apps import apps


@dataclasses.dataclass(frozen=True)
class Ref:
    type: str
    id: int
    name: str | None


# Reference type -> (model, attribute holding its display name; None shows "#<id>").
REFERENCE_TYPES: dict[str, tuple[str, str | None]] = {
    "algorithm": ("ml.Algorithm", "name"),
    "capture_set": ("main.SourceImageCollection", "name"),
    "job": ("jobs.Job", "name"),
    "occurrence": ("main.Occurrence", None),
    "taxa_list": ("main.TaxaList", "name"),
    "taxon": ("main.Taxon", "name"),
}

# Job settings (post-processing configs) that hold another record's id.
JOB_SETTING_REFERENCES: dict[str, str] = {
    "source_image_collection_id": "capture_set",
    "taxa_list_id": "taxa_list",
    "algorithm_id": "algorithm",
    "occurrence_id": "occurrence",
}


def job_setting_references(config: typing.Any) -> list[tuple[str, str, int]]:
    """``(setting key, reference type, id)`` for each job setting that names another record."""
    if not isinstance(config, dict):
        return []
    return [
        (key, ref_type, config[key])
        for key, ref_type in JOB_SETTING_REFERENCES.items()
        if isinstance(config.get(key), int) and not isinstance(config.get(key), bool)
    ]


def resolve_references(wanted: typing.Iterable[tuple[str, int]]) -> dict[tuple[str, int], Ref]:
    """Each ``(type, id)`` as a ``Ref``, reading names with one query per type.

    An unknown type raises KeyError: a result kind declared a reference type nobody mapped.
    """
    ids_by_type: dict[str, set[int]] = collections.defaultdict(set)
    for ref_type, ref_id in wanted:
        ids_by_type[ref_type].add(ref_id)
    resolved: dict[tuple[str, int], Ref] = {}
    for ref_type, ids in ids_by_type.items():
        model_label, name_attr = REFERENCE_TYPES[ref_type]
        model = apps.get_model(model_label)
        if name_attr is None:
            names = {pk: f"#{pk}" for pk in model.objects.filter(pk__in=ids).values_list("pk", flat=True)}
        else:
            names = dict(model.objects.filter(pk__in=ids).values_list("pk", name_attr))
        for ref_id in ids:
            resolved[(ref_type, ref_id)] = Ref(ref_type, ref_id, names.get(ref_id))
    return resolved
