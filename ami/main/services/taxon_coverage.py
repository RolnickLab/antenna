"""Keep `Taxon.covered_by_algorithms` / `Taxon.has_model_coverage` in sync with what
classifiers can actually predict.

Coverage is derived data: a taxon is "covered" by an algorithm when the taxon's name
appears in that algorithm's category map labels — the same `Taxon.name == label` join
`AlgorithmCategoryMap.with_taxa()` uses at classification time (`ami/ml/models/algorithm.py`).
It is computed here and persisted so callers (the regional taxa-list service, the admin,
future masking auto-resolution) can filter/read it without re-deriving the join on every
request. It is never recomputed on a per-occurrence or per-classification basis — only
when a category map's label set changes (see the `Algorithm.save()` hook) or on demand via
the `refresh_taxon_model_coverage` management command, so a brief lag between a label-set
change and this flag updating is expected and harmless (masking itself still resolves names
live via `with_taxa()`; this flag is a filtering/reporting convenience, not the masking path).
"""

import typing

from ..models import Taxon

if typing.TYPE_CHECKING:
    from ami.ml.models.algorithm import Algorithm


def refresh_algorithm_coverage(algorithm: "Algorithm") -> None:
    """Recompute which Taxon rows `algorithm` covers, from its category map's label
    set, and persist has_model_coverage for every taxon whose membership changed
    (both the ones that gained coverage and the ones that lost it).

    Call this whenever an algorithm starts, stops, or changes which category map it
    uses — the `Algorithm.save()` hook does this automatically when `category_map_id`
    changes. An algorithm with no category map covers nothing.
    """
    category_map = algorithm.category_map
    new_taxon_ids: set[int] = set()
    if category_map is not None and category_map.labels:
        new_taxon_ids = set(Taxon.objects.filter(name__in=category_map.labels).values_list("pk", flat=True))

    old_taxon_ids = set(algorithm.covered_taxa.values_list("pk", flat=True))
    algorithm.covered_taxa.set(Taxon.objects.filter(pk__in=new_taxon_ids))
    _resync_has_model_coverage(old_taxon_ids | new_taxon_ids)


def refresh_all_algorithm_coverage() -> int:
    """Rebuild the model-coverage relationship for every algorithm that has a
    category map. This is the full-rebuild path: the `refresh_taxon_model_coverage`
    management command uses it for the initial backfill and as a repair tool, and the
    regional taxa-list service uses it to give freshly created Taxon rows a coverage
    state before partitioning them (they have none yet, having just been created).

    Cost is one query per algorithm (best-guess, not measured against a
    production-sized category map / algorithm count) — see plan issue #1364 §14 for
    the open question of whether this needs to move off the request path for large
    deployments.

    Returns the number of algorithms processed.
    """
    from ami.ml.models.algorithm import Algorithm

    algorithms = list(Algorithm.objects.filter(category_map__isnull=False).select_related("category_map"))
    for algorithm in algorithms:
        refresh_algorithm_coverage(algorithm)
    return len(algorithms)


def names_covered_by_any_algorithm(names: set[str]) -> set[str]:
    """Read-only check of which of `names` appear in some algorithm's category map
    labels, without creating or persisting anything. Used only to simulate the
    model-coverage partition for species that don't have a Taxon row yet (the
    dry_run path of `generate_regional_taxa_list`, which must not mutate the DB).
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
