"""Record ids stored in JSON, resolved to ``{type, id, name}`` so the UI can show and link them.

A model opts in by declaring ``reference_type`` (and ``reference_name_field``, the attribute shown
as its name; None shows ``#<id>``). A pydantic schema marks a field that holds such an id with
``reference()``. ``resolve_references`` reads the names with one query per type, and the UI maps
each type to a page in ``ui/src/utils/references.ts``.
"""

import collections
import dataclasses
import functools
import typing

import pydantic
from django.apps import apps


@dataclasses.dataclass(frozen=True)
class Ref:
    """A record a stored value names. ``name`` is None when the record no longer exists."""

    type: str
    id: int
    name: str | None


def reference(ref_type: str, default: typing.Any = None, **field_options: typing.Any) -> typing.Any:
    """Declare a pydantic field that holds the id of a record of ``ref_type``.

    ``field_options`` go to ``pydantic.Field``.
    """
    return pydantic.Field(default, reference=ref_type, **field_options)


def field_references(schema: type[pydantic.BaseModel]) -> dict[str, str]:
    """The schema's fields declared with ``reference()``, mapped to the reference type."""
    return {
        name: field.field_info.extra["reference"]
        for name, field in schema.__fields__.items()
        if "reference" in field.field_info.extra
    }


def field_titles(schema: type[pydantic.BaseModel]) -> dict[str, str | None]:
    """Every field of the schema, in declaration order, mapped to its ``title`` or None."""
    return {name: field.field_info.title for name, field in schema.__fields__.items()}


def is_record_id(value: typing.Any) -> bool:
    """Whether a stored value can be a primary key: an int that is not a bool."""
    return isinstance(value, int) and not isinstance(value, bool)


@functools.cache
def reference_types() -> dict[str, tuple[type, str | None]]:
    """Each declared reference type mapped to its model and name field."""
    types: dict[str, tuple[type, str | None]] = {}
    for model in apps.get_models():
        ref_type = getattr(model, "reference_type", None)
        if ref_type is None:
            continue
        if ref_type in types:
            raise ValueError(f"Reference type {ref_type!r} is declared by {types[ref_type][0]} and {model}.")
        types[ref_type] = (model, getattr(model, "reference_name_field", None))
    return types


def unmapped_reference_types(schemas: typing.Iterable[type[pydantic.BaseModel]]) -> set[str]:
    """Reference types the schemas declare that no model declares; resolving them would fail."""
    declared = {ref_type for schema in schemas for ref_type in field_references(schema).values()}
    return declared - set(reference_types())


def resolve_references(wanted: typing.Iterable[tuple[str, int]]) -> dict[tuple[str, int], Ref]:
    """Each ``(type, id)`` as a ``Ref``, reading names with one query per type.

    An unknown type raises KeyError: a schema declared a reference type no model declares.
    """
    ids_by_type: dict[str, set[int]] = collections.defaultdict(set)
    for ref_type, ref_id in wanted:
        ids_by_type[ref_type].add(ref_id)
    resolved: dict[tuple[str, int], Ref] = {}
    for ref_type, ids in ids_by_type.items():
        model, name_field = reference_types()[ref_type]
        if name_field is None:
            names = {pk: f"#{pk}" for pk in model.objects.filter(pk__in=ids).values_list("pk", flat=True)}
        else:
            names = dict(model.objects.filter(pk__in=ids).values_list("pk", name_field))
        for ref_id in ids:
            resolved[(ref_type, ref_id)] = Ref(ref_type, ref_id, names.get(ref_id))
    return resolved
