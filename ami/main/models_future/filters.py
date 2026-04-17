"""
This module provides reusable Q filter builders for database queries.
"""

from typing import TYPE_CHECKING

from django.db import models
from django.db.models import Q

if TYPE_CHECKING:
    from ami.main.models import Project, Taxon
    from rest_framework.request import Request

from ami.utils.requests import get_apply_default_filters_flag, get_default_classification_threshold


def build_taxa_recursive_filter_q(
    include_taxa: models.QuerySet["Taxon"] | None = None,
    exclude_taxa: models.QuerySet["Taxon"] | None = None,
    taxon_accessor: str = "",
) -> Q:
    """
    Build a Q filter for taxa inclusion/exclusion (including descendants via parents_json).

    This handles the hierarchy traversal for taxa filtering, supporting both inclusion
    and exclusion in a single unified method.

    Args:
        include_taxa: QuerySet of taxa to include (if any)
        exclude_taxa: QuerySet of taxa to exclude (if any)
        taxon_accessor: Path to the taxon field (without trailing __):
            - "": Direct Taxon model (uses id__in, parents_json__contains)
            - "determination": Occurrence's determination field
            - "occurrences__determination": Event→Occurrence→determination
            - "detections__occurrence__determination": Image→Detection→Occurrence→determination
            - "images__detections__occurrence__determination": Collection→...

    Returns:
        Q object for filtering by included/excluded taxa and their descendants

    Examples:
        Direct Taxa model filtering:
            >>> include_taxa = project.default_filters_include_taxa.all()
            >>> exclude_taxa = project.default_filters_exclude_taxa.all()
            >>> taxa_q = build_taxa_recursive_filter_q(include_taxa, exclude_taxa, taxon_accessor="")
            >>> taxa = Taxon.objects.filter(taxa_q)

        Combining with other filters:
            >>> score_q = build_occurrence_score_threshold_q(0.8, "")
            >>> taxa_q = build_taxa_recursive_filter_q(include_taxa, exclude_taxa, "determination")
            >>> combined_q = score_q & taxa_q & Q(determination__isnull=False)
            >>> occurrences = Occurrence.objects.filter(combined_q)
    """
    result_q = Q()

    # Determine field names based on taxon_accessor
    if taxon_accessor:
        # For filtering through relationships, add __ separator and use the accessor path
        id_field = f"{taxon_accessor}__id__in"
        parents_field = f"{taxon_accessor}__parents_json__contains"
    else:
        # For direct Taxon model filtering
        id_field = "id__in"
        parents_field = "parents_json__contains"

    # Handle inclusion
    if include_taxa and include_taxa.exists():
        # Start with direct match
        include_q = Q(**{id_field: include_taxa})

        # Add descendants via parents_json traversal
        for taxon in include_taxa:
            include_q |= Q(**{parents_field: [{"id": taxon.pk}]})

        result_q &= include_q

    # Handle exclusion
    if exclude_taxa and exclude_taxa.exists():
        # Start with direct match
        exclude_q = Q(**{id_field: exclude_taxa})

        # Add descendants via parents_json traversal
        for taxon in exclude_taxa:
            exclude_q |= Q(**{parents_field: [{"id": taxon.pk}]})

        result_q &= ~exclude_q

    return result_q


def build_occurrence_score_threshold_q(
    score_threshold: float,
    occurrence_accessor: str = "",
) -> Q:
    """
    Build a Q filter for minimum determination score threshold on Occurrence relationships.

    This function is specifically for filtering occurrences (and models with occurrence
    relationships) by their determination score. For direct Taxa filtering, use
    build_taxa_recursive_filter_q() instead.

    Args:
        score_threshold: Minimum score value to filter by
        occurrence_accessor: Path to the Occurrence model (function adds __ and field name):
            - "": Direct Occurrence → determination_score__gte
            - "occurrences": Event → occurrences__determination_score__gte
            - "detections__occurrence": Image → detections__occurrence__determination_score__gte
            - "images__detections__occurrence": Collection →
              images__detections__occurrence__determination_score__gte

    Returns:
        Q object for score threshold filtering

    Examples:
        Direct occurrence filtering with custom threshold:
            >>> score_q = build_occurrence_score_threshold_q(0.9, occurrence_accessor="")
            >>> high_confidence = Occurrence.objects.filter(score_q)

        Event-level filtering:
            >>> score_q = build_occurrence_score_threshold_q(0.8, occurrence_accessor="occurrences")
            >>> events = Event.objects.filter(score_q).distinct()
    """
    # Add __ separator if accessor is not empty
    prefix = f"{occurrence_accessor}__" if occurrence_accessor else ""
    return Q(**{f"{prefix}determination_score__gte": score_threshold})


def build_occurrence_default_filters_q(
    project: "Project | None" = None,
    request: "Request | None" = None,
    occurrence_accessor: str = "",
    apply_default_score_filter: bool = True,
    apply_default_taxa_filter: bool = True,
) -> Q:
    """
    Build a Q filter that applies default filters (score threshold + taxa) for Occurrence relationships.

    This is specifically for filtering occurrences and models with occurrence relationships.
    For direct Taxa model filtering, use build_taxa_recursive_filter_q() with taxon_accessor="".

    This method respects the apply_defaults flag from the request. If apply_defaults=false,
    it returns an empty Q() object (no filtering applied).

    Args:
        project: The project whose default filters should be applied
        request: The request object (used to get apply_defaults flag and threshold values)
        occurrence_accessor: Path to the Occurrence model (without trailing __):
            - "": Direct Occurrence
            - "occurrences": Event→Occurrence
            - "detections__occurrence": Image→Detection→Occurrence
            - "images__detections__occurrence": Collection→...

    Returns:
        Q object that can be used in filters or annotations.
        Returns Q() if apply_defaults=false.

    Examples:
        Direct Occurrence filtering:
            >>> filter_q = build_occurrence_default_filters_q(project, request, occurrence_accessor="")
            >>> occurrences = Occurrence.objects.filter(filter_q)

        Event with occurrence counts:
            >>> filter_q = build_occurrence_default_filters_q(project, request, occurrence_accessor="occurrences")
            >>> events = Event.objects.annotate(
            ...     filtered_occ_count=Count('occurrences', filter=filter_q, distinct=True),
            ...     filtered_taxa_count=Count('occurrences__determination', filter=filter_q, distinct=True)
            ... ).filter(filtered_occ_count__gt=0)

        SourceImage with detection counts:
            >>> filter_q = build_occurrence_default_filters_q(
            ...     project, request, occurrence_accessor="detections__occurrence"
            ... )
            >>> images = SourceImage.objects.annotate(
            ...     filtered_count=Count('detections__occurrence', filter=filter_q, distinct=True)
            ... ).filter(filtered_count__gt=0)

        Collection with nested relationships:
            >>> filter_q = build_occurrence_default_filters_q(
            ...     project, request, occurrence_accessor="images__detections__occurrence"
            ... )
            >>> collections = SourceImageCollection.objects.annotate(
            ...     occ_count=Count('images__detections__occurrence', filter=filter_q, distinct=True),
            ...     taxa_count=Count('images__detections__occurrence__determination', filter=filter_q, distinct=True)
            ... )

        Bypassing default filters (pass apply_defaults=false in query params):
            >>> # Example: /api/occurrences/?apply_defaults=false
            >>> filter_q = build_occurrence_default_filters_q(project, request, occurrence_accessor="")
            >>> # Returns Q() - no filtering applied
    """
    if project is None:
        return Q()

    # Check apply_defaults flag - if False, return empty Q (no filtering)
    if get_apply_default_filters_flag(request) is False:
        return Q()

    filter_q = Q()
    if apply_default_score_filter:
        # Build score threshold filter
        score_threshold = get_default_classification_threshold(project, request)
        filter_q &= build_occurrence_score_threshold_q(score_threshold, occurrence_accessor)
    if apply_default_taxa_filter:
        # Build taxa inclusion/exclusion filter
        # For taxa filtering, we need to append "__determination" to the occurrence accessor
        prefix = f"{occurrence_accessor}__" if occurrence_accessor else ""
        taxon_accessor = f"{prefix}determination"
        include_taxa = project.default_filters_include_taxa.all()
        exclude_taxa = project.default_filters_exclude_taxa.all()
        taxa_q = build_taxa_recursive_filter_q(include_taxa, exclude_taxa, taxon_accessor)
        if taxa_q:
            filter_q &= taxa_q

    return filter_q
