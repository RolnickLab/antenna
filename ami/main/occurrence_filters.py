"""The occurrence list's filter parameters, defined once, and a way to apply them without a request.

``OccurrenceFilterSet`` declares every query parameter that narrows the occurrence list. The list,
the occurrence stats and exports all apply it, so the same parameters select the same occurrences
everywhere. Filters saved for later, such as an export's ``filters``, are checked and normalised by
``clean_saved_filters()`` and applied by ``filter_occurrences()``. See #1537.
"""

import datetime
import functools
import typing

from django import forms
from django.db import models
from django.db.models import Q
from django_filters import rest_framework as filters
from django_filters.constants import EMPTY_VALUES
from django_filters.utils import get_model_field, translate_validation
from rest_framework import exceptions as api_exceptions

from ami.base.filters import IntegerListFilter, QueryBooleanField, QueryBooleanFilter, RelatedIdFilter
from ami.base.model_references import ModelRef, resolve_model_references
from ami.main.models import Occurrence, OccurrenceQuerySet, Project, TaxaList, Taxon

# Other names for a parameter, mapped to the name they stand for. When both have a value, the
# canonical name wins. Saved filters store the canonical name.
PARAMETER_ALIASES = {
    "taxon": "determination",
    "collection": "collection_id",  # @TODO remove "collection" when the UI sends collection_id
}

# Parameters that switch the project's default filters on or off. ``apply_default_filters()``
# reads them before the FilterSet runs, so they are not FilterSet filters.
DEFAULT_FILTER_PARAMS = ("apply_defaults",)

# Parameters whose result depends on who asks. Saved filters are applied later, by a job or for
# another user, so they cannot hold these.
USER_DEPENDENT_PARAMS = ("verified_by_me",)


class OccurrenceFilterForm(forms.Form):
    """Resolves parameter aliases and checks the values that depend on each other."""

    def clean(self):
        cleaned = super().clean()
        given_as = {}
        for alias, name in PARAMETER_ALIASES.items():
            given_as[name] = name if cleaned.get(name) else alias
            if not cleaned.get(name):
                cleaned[name] = cleaned.get(alias)
            cleaned[alias] = None

        date_start, date_end = cleaned.get("date_start"), cleaned.get("date_end")
        if date_start and date_end and date_start > date_end:
            self.add_error("date_start", "Start date must be before end date")

        taxon_id = cleaned.get("determination")
        if taxon_id and not Taxon.objects.filter(pk=taxon_id).exists():
            self.add_error(given_as["determination"], f"No taxon found with id {taxon_id}")
        return cleaned


class OccurrenceFilterSet(filters.FilterSet):
    """Every query parameter that narrows the occurrence list, its stats and exports.

    The declared filters on related records take a plain id, so the browsable API form does not
    list those tables. Each filter's ``field_name`` is the path from an occurrence to the record it
    names; ``filter_reference_types()`` reads it to show saved filters by name.
    """

    detections__source_image = RelatedIdFilter()

    determination = RelatedIdFilter(
        field_name="determination",
        method="filter_determination",
        help_text="Occurrences determined as this taxon or any of its child taxa.",
    )
    taxon = RelatedIdFilter(
        field_name="determination",
        method="filter_determination",
        help_text="Another name for `determination`.",
    )
    collection_id = RelatedIdFilter(
        field_name="detections__source_image__collections",
        method="filter_collection",
        help_text="Occurrences with a detection in a capture of this capture set.",
    )
    collection = RelatedIdFilter(
        field_name="detections__source_image__collections",
        method="filter_collection",
        help_text="Deprecated name for `collection_id`.",
    )
    algorithm = IntegerListFilter(
        field_name="detections__classifications__algorithm",
        method="filter_algorithm",
        help_text="Occurrences with a detection or classification made by any of these algorithms. Repeatable.",
    )
    not_algorithm = IntegerListFilter(
        field_name="detections__classifications__algorithm",
        method="filter_not_algorithm",
        help_text="Occurrences with no detection or classification made by any of these algorithms. Repeatable.",
    )
    job = RelatedIdFilter(
        field_name="detections__job",
        method="filter_job",
        min_value=1,
        help_text="Occurrences created or updated by this job.",
    )
    date_start = filters.DateFilter(
        field_name="detections__timestamp",
        method="filter_date_start",
        input_formats=["%Y-%m-%d"],
        help_text="Occurrences with a detection on or after this date (YYYY-MM-DD).",
    )
    date_end = filters.DateFilter(
        field_name="detections__timestamp",
        method="filter_date_end",
        input_formats=["%Y-%m-%d"],
        help_text="Occurrences with a detection on or before this date (YYYY-MM-DD).",
    )
    verified = QueryBooleanFilter(
        field_name="identifications",
        method="filter_verified",
        help_text="Occurrences that someone has identified (true) or that no one has identified (false).",
    )
    verified_by_me = QueryBooleanFilter(
        field_name="identifications__user",
        method="filter_verified_by_me",
        help_text="Occurrences that the signed-in user has identified (true) or has not identified (false).",
    )
    taxa_list_id = RelatedIdFilter(
        field_name="determination__lists",
        method="filter_taxa_list",
        help_text="Occurrences determined as a taxon in this taxa list or a descendant of one.",
    )
    not_taxa_list_id = RelatedIdFilter(
        field_name="determination__lists",
        method="filter_not_taxa_list",
        help_text="Occurrences not determined as a taxon in this taxa list or a descendant of one.",
    )

    class Meta:
        model = Occurrence
        form = OccurrenceFilterForm
        fields = [
            "event",
            "deployment",
            "deployment__device",
            "deployment__research_site",
            "determination__rank",
            "detections__source_image",
        ]

    def filter_determination(self, queryset, name, value):
        # The literal parents_json containment (constant RHS) is what the GIN index from
        # migration 0087 serves — this hierarchical taxon filter is the index's main consumer.
        return queryset.filter(Q(determination=value) | Q(determination__parents_json__contains=[{"id": value}]))

    def filter_collection(self, queryset, name, value):
        return queryset.filter(detections__source_image__collections=value) if value else queryset

    def filter_algorithm(self, queryset, name, value):
        return queryset.processed_by_algorithm(value)

    def filter_not_algorithm(self, queryset, name, value):
        return queryset.not_processed_by_algorithm(value)

    def filter_job(self, queryset, name, value):
        return queryset.created_or_updated_by_job(value)

    def filter_date_start(self, queryset, name, value):
        return queryset.filter(detections__timestamp__date__gte=value)

    def filter_date_end(self, queryset, name, value):
        return queryset.filter(detections__timestamp__date__lte=value)

    def filter_verified(self, queryset, name, value):
        return queryset.filter(identifications__isnull=not value)

    def filter_verified_by_me(self, queryset, name, value):
        user = getattr(self.request, "user", None)
        if not (user and user.is_authenticated):
            return queryset
        if value:
            return queryset.filter(identifications__user=user)
        return queryset.exclude(identifications__user=user)

    def filter_taxa_list(self, queryset, name, value):
        taxa_q = self._taxa_list_q(value)
        return queryset.filter(taxa_q) if taxa_q is not None else queryset

    def filter_not_taxa_list(self, queryset, name, value):
        taxa_q = self._taxa_list_q(value)
        return queryset.exclude(taxa_q) if taxa_q is not None else queryset

    @staticmethod
    def _taxa_list_q(taxa_list_id: int) -> Q | None:
        """Determined as a taxon of the list or a descendant of one; None when the list does not exist."""
        taxa_list = TaxaList.objects.filter(id=taxa_list_id).first()
        if not taxa_list:
            return None
        taxa = taxa_list.taxa.all()
        taxa_q = Q(determination__in=taxa)
        for taxon in taxa:
            taxa_q |= Q(determination__parents_json__contains=[{"id": taxon.pk}])
        return taxa_q


def saved_filter_params() -> set[str]:
    """Every parameter that saved occurrence filters may hold."""
    return (set(OccurrenceFilterSet.base_filters) | set(DEFAULT_FILTER_PARAMS)) - set(USER_DEPENDENT_PARAMS)


def _parse_saved_filters(saved: typing.Any) -> tuple[dict[str, typing.Any], bool]:
    """Split saved filters into FilterSet parameters and the ``apply_defaults`` choice.

    Raises a DRF ``ValidationError`` for anything that is not a dict of known parameters.
    """
    if saved is None:
        saved = {}
    if not isinstance(saved, dict):
        raise api_exceptions.ValidationError(["Filters must be an object of parameter names and values."])
    errors: dict[str, list[str]] = {}
    known = saved_filter_params()
    for key in saved:
        if key in USER_DEPENDENT_PARAMS:
            errors[key] = ["This filter depends on who is signed in, so it cannot be saved."]
        elif key not in known:
            errors[key] = ["Unknown filter."]

    # As on the occurrence list, an absent or blank apply_defaults means true.
    apply_defaults = saved.get("apply_defaults")
    if apply_defaults in (None, ""):
        apply_defaults = True
    else:
        try:
            apply_defaults = QueryBooleanField().clean(apply_defaults)
        except forms.ValidationError as e:
            errors["apply_defaults"] = e.messages
    if errors:
        raise api_exceptions.ValidationError(errors)

    params = {key: value for key, value in saved.items() if key not in DEFAULT_FILTER_PARAMS}
    return params, apply_defaults


def _validated_filterset(params: dict[str, typing.Any], queryset) -> OccurrenceFilterSet:
    # No request: the parameters that need one (verified_by_me) are refused before this point.
    filterset = OccurrenceFilterSet(data=params, queryset=queryset, request=None)
    if not filterset.is_valid():
        raise translate_validation(filterset.errors)
    return filterset


def _json_value(value: typing.Any) -> typing.Any:
    """A cleaned filter value as JSON: a record as its id, a date as ``YYYY-MM-DD``."""
    if isinstance(value, models.Model):
        return value.pk
    if isinstance(value, datetime.date):
        return value.isoformat()
    return value


def clean_saved_filters(saved: typing.Any) -> dict[str, typing.Any]:
    """Check occurrence filters before they are saved, and return them in a normal form.

    The normal form holds the typed values the FilterSet cleaned (ids as numbers, dates as
    ``YYYY-MM-DD``, true or false), canonical names instead of aliases, no blank values, and
    always ``apply_defaults``, so two equal filters compare equal. Raises a DRF
    ``ValidationError`` with one entry for each bad or unknown parameter.
    """
    params, apply_defaults = _parse_saved_filters(saved)
    filterset = _validated_filterset(params, Occurrence.objects.none())
    cleaned = {
        name: _json_value(value) for name, value in filterset.form.cleaned_data.items() if value not in EMPTY_VALUES
    }
    cleaned["apply_defaults"] = apply_defaults
    return cleaned


def filter_occurrences(
    project: Project, saved: typing.Any, queryset: OccurrenceQuerySet | None = None
) -> OccurrenceQuerySet:
    """The project's occurrences that the occurrence list returns for these saved filters.

    Applies the project's default filters unless ``apply_defaults`` is false, then the
    ``OccurrenceFilterSet``, in the same order as the list. Raises a DRF ``ValidationError`` as
    ``clean_saved_filters()`` does.

    ``queryset`` lets a caller add its own annotations and prefetches. It must already be limited
    to the project's valid occurrences, and should group by occurrence (as the count annotations of
    the list and the exporters do): the date and capture set filters join detections, so without
    grouping an occurrence repeats once per matching detection. Without ``queryset``, each
    occurrence is returned once.
    """
    params, apply_defaults = _parse_saved_filters(saved)
    own_queryset = queryset is None
    if queryset is None:
        queryset = Occurrence.objects.valid().filter(project=project)  # type: ignore[union-attr]
    if apply_defaults:
        queryset = queryset.apply_default_filters(project)  # type: ignore[union-attr]
    filtered = _validated_filterset(params, queryset).qs
    if own_queryset:
        return Occurrence.objects.filter(pk__in=filtered.values("pk"))  # type: ignore[return-value]
    return filtered


@functools.cache
def filter_reference_types() -> dict[str, str]:
    """Each filter that takes the id of a record, mapped to that record's reference type.

    Read from the model at the end of each filter's ``field_name``, so a new filter on a model
    that declares a ``reference_type`` is shown by name without being listed here.
    """
    types = {}
    for name, filter_ in OccurrenceFilterSet.base_filters.items():
        field = get_model_field(Occurrence, filter_.field_name)
        ref_type = getattr(getattr(field, "related_model", None), "reference_type", None)
        if ref_type:
            types[name] = ref_type
    return types


def _record_ids(value: typing.Any) -> list[int] | None:
    """The ids a saved value names, or None if it is not ids.

    Exports saved before their filters were validated can hold ids as strings.
    """
    items = value if isinstance(value, list) else [value]
    ids = []
    for item in items:
        if isinstance(item, bool):
            return None
        if isinstance(item, int):
            ids.append(item)
        elif isinstance(item, str) and item.isdigit():
            ids.append(int(item))
        else:
            return None
    return ids


def describe_saved_filters(saved: dict[str, typing.Any] | None) -> dict[str, typing.Any]:
    """Saved filters as the UI shows them: each record id with its type and name.

    A filter on a record becomes ``{"type", "id", "name"}`` (a list of them for a repeatable
    filter) under its name without ``_id``; ``name`` is None when the record no longer exists.
    Other values are kept as they are. Reads names with one query per record type.
    """
    saved = saved or {}
    reference_types = filter_reference_types()
    wanted: dict[str, tuple[str, list[int]]] = {}
    for key, value in saved.items():
        ids = _record_ids(value) if key in reference_types else None
        if ids:
            wanted[key] = (reference_types[key], ids)
    resolved = resolve_model_references((ref_type, i) for ref_type, ids in wanted.values() for i in ids)

    def as_dict(ref: ModelRef) -> dict[str, typing.Any]:
        return {"type": ref.type, "id": ref.id, "name": ref.name}

    display: dict[str, typing.Any] = {}
    for key, value in saved.items():
        if key not in wanted:
            display[key] = value
            continue
        ref_type, ids = wanted[key]
        refs = [as_dict(resolved[(ref_type, i)]) for i in ids]
        display[key.removesuffix("_id")] = refs if isinstance(value, list) else refs[0]
    return display
