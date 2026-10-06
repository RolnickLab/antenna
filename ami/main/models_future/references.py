"""Ids the occurrence history shows, resolved to ``{type, id, name}`` so the UI can link them with one table.

``name`` is None when the row no longer exists; the UI then shows the id as text. Resolution reads names
only, one query per type, and is used for ids stored on the occurrence's own results and jobs. Result data
models and task config schemas declare which fields hold an id with ``ami.ml.results.schemas.reference``.
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


def is_record_id(value: typing.Any) -> bool:
    """Whether a stored value can be a primary key: an int that is not a bool."""
    return isinstance(value, int) and not isinstance(value, bool)


def unmapped_reference_types(models: typing.Iterable[type] | None = None) -> set[str]:
    """Reference types that result data models or task config schemas declare but this module does not map.

    Defaults to every registered result kind and post-processing task; a test keeps the answer empty.
    """
    from ami.ml.results.schemas import ALGORITHM_RESULT_DATA_MODELS, field_references

    if models is None:
        from ami.ml.post_processing.registry import POSTPROCESSING_TASKS

        models = [*ALGORITHM_RESULT_DATA_MODELS, *(task.config_schema for task in POSTPROCESSING_TASKS.values())]
    return {ref_type for model in models for ref_type in field_references(model).values()} - set(REFERENCE_TYPES)


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
