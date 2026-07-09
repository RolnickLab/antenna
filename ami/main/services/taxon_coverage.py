"""Keep `Taxon.covered_by_algorithms` / `Taxon.has_model_coverage` in sync with what
classifiers can actually predict.

Coverage is derived data: a taxon is "covered" by an algorithm when the algorithm's
category map resolves one of its labels to that taxon — the *same* resolution masking
uses at classification time. To guarantee the flag can never disagree with masking,
coverage is derived from `AlgorithmCategoryMap.with_taxa()` itself
(`ami/ml/models/algorithm.py`) rather than a re-implemented label query: `with_taxa`
maps a label to the active `Taxon` whose name equals it, so an inactive taxon, or one
whose name does not exactly match a label, is not covered — exactly as masking behaves.

It is computed here and persisted so callers (the regional taxa-list service, the admin,
masking auto-resolution) can filter/read it cheaply. It is recomputed when a category
map's label set changes (the `AlgorithmCategoryMap.save()` and `Algorithm.save()` hooks)
or on demand via the `refresh_taxon_model_coverage` command — never per occurrence or
per classification. A brief lag between a label-set change and this flag updating is
harmless: masking itself always resolves names live via `with_taxa()`; this flag is a
filtering/reporting convenience, not the masking path.
"""

import typing

from ..models import Taxon

if typing.TYPE_CHECKING:
    from ami.ml.models.algorithm import Algorithm, AlgorithmCategoryMap


def _covered_taxon_ids_for_map(category_map: "AlgorithmCategoryMap") -> set[int]:
    """Taxon ids this category map covers.

    This replicates the EFFECTIVE resolution of `AlgorithmCategoryMap.with_taxa()`: a
    label maps to the active `Taxon` whose name equals it. `with_taxa()` builds its
    lookup keyed by taxon name (`{taxon.name: taxon}`) and looks up by label, so only
    active, exact-name taxa are ever attributed — the `search_names` term in its query
    never changes the result. We deliberately do NOT call `with_taxa()` here because it
    mutates the map's `data` in place (embedding Taxon objects, which then break JSON
    serialization of the field). The `active=True` filter is the part the earlier
    name-only coverage query was missing. If `with_taxa()`'s matching ever broadens
    (e.g. to actually honour `search_names`), update this in step.
    """
    if category_map is None or not category_map.labels:
        return set()
    return set(Taxon.objects.filter(name__in=category_map.labels, active=True).values_list("pk", flat=True))


def refresh_category_map_coverage(category_map: "AlgorithmCategoryMap") -> None:
    """Recompute `covered_taxa` for every algorithm using this category map, then
    resync `has_model_coverage` for the affected taxa.

    Membership is computed once per map and fanned out to its algorithms, so ten
    algorithms sharing one map cost one label resolution, not ten.
    """
    covered_ids = _covered_taxon_ids_for_map(category_map)
    affected: set[int] = set(covered_ids)
    for algorithm in category_map.algorithms.all():
        affected |= set(algorithm.covered_taxa.values_list("pk", flat=True))
        algorithm.covered_taxa.set(covered_ids)
    _resync_has_model_coverage(affected)


def refresh_algorithm_coverage(algorithm: "Algorithm") -> None:
    """Recompute coverage for one algorithm — through its whole category map, so any
    algorithms sharing that map stay consistent. Called by the `Algorithm.save()` hook
    when `category_map_id` changes. An algorithm with no category map covers nothing.
    """
    if algorithm.category_map_id is None:
        old_taxon_ids = set(algorithm.covered_taxa.values_list("pk", flat=True))
        algorithm.covered_taxa.clear()
        _resync_has_model_coverage(old_taxon_ids)
        return
    refresh_category_map_coverage(algorithm.category_map)


def refresh_all_algorithm_coverage() -> int:
    """Rebuild the coverage relationship for every category map — the full backfill and
    repair path used by the initial data migration and the `refresh_taxon_model_coverage`
    command. Returns the number of category maps processed.
    """
    from ami.ml.models.algorithm import AlgorithmCategoryMap

    category_maps = list(AlgorithmCategoryMap.objects.all())
    for category_map in category_maps:
        refresh_category_map_coverage(category_map)
    return len(category_maps)


def refresh_coverage_for_taxa(taxon_ids: typing.Iterable[int]) -> None:
    """Compute and persist coverage for exactly these taxa, without a full rebuild.

    For taxa the regional service just created, this links each to any algorithm whose
    category map covers it (using the same `with_taxa()` resolution as everywhere else),
    then resyncs `has_model_coverage` for only these taxa. It loads only the category
    maps whose labels overlap these taxa's names, so the `--all-projects` backfill cost
    scales with the newly created taxa, not the total algorithm/label count.
    """
    from ami.ml.models.algorithm import AlgorithmCategoryMap

    taxon_ids = list(taxon_ids)
    if not taxon_ids:
        return

    ours = set(taxon_ids)
    names = list(Taxon.objects.filter(pk__in=taxon_ids).values_list("name", flat=True))
    if names:
        for category_map in AlgorithmCategoryMap.objects.filter(labels__overlap=names):
            matched = ours & _covered_taxon_ids_for_map(category_map)
            if not matched:
                continue
            for algorithm in category_map.algorithms.all():
                algorithm.covered_taxa.add(*matched)
    _resync_has_model_coverage(taxon_ids)


def names_covered_by_any_algorithm(names: set[str]) -> set[str]:
    """Read-only check of which of `names` appear in some algorithm's category map
    labels, without creating or persisting anything. Used only to simulate the
    model-coverage partition for species that don't have a Taxon row yet (the
    dry_run path of `generate_regional_taxa_list`, which must not mutate the DB). A
    species created from a source is active, so name-in-labels matches what masking
    would keep once the row exists.
    """
    from ami.ml.models.algorithm import AlgorithmCategoryMap

    if not names:
        return set()
    covered: set[str] = set()
    for category_map in AlgorithmCategoryMap.objects.only("labels"):
        covered |= names.intersection(category_map.labels)
        if covered == names:
            break
    return covered


def _resync_has_model_coverage(taxon_ids: typing.Iterable[int]) -> None:
    """Set has_model_coverage = (covered_by_algorithms is non-empty) for exactly
    these taxa, in two bulk UPDATEs — no per-row queries."""
    taxon_ids = list(taxon_ids)
    if not taxon_ids:
        return
    covered_ids = set(
        Taxon.objects.filter(pk__in=taxon_ids, covered_by_algorithms__isnull=False)
        .values_list("pk", flat=True)
        .distinct()
    )
    uncovered_ids = set(taxon_ids) - covered_ids
    if covered_ids:
        Taxon.objects.filter(pk__in=covered_ids).update(has_model_coverage=True)
    if uncovered_ids:
        Taxon.objects.filter(pk__in=uncovered_ids).update(has_model_coverage=False)
