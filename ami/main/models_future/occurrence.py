"""
Reusable Prefetch factories and aggregate queries for Occurrence rendering.

The serializer trusts the prefetch contract — the viewset is the single place
that wires it up. Don't gate serializer methods on `_prefetched_objects_cache`
membership; require the prefetch.

Tracking issue: https://github.com/RolnickLab/antenna/issues/1271
"""

from __future__ import annotations

import collections
import math
from typing import TYPE_CHECKING

from django.db.models import Count, OuterRef, Prefetch, Q, QuerySet, Subquery

from ami.main.models import Project, TaxonRank, User

if TYPE_CHECKING:
    from ami.main.models import Classification, Identification, Occurrence

TaxonTuple = tuple[int, str, list[dict]]


def lca_rank_between(a: TaxonTuple, b: TaxonTuple) -> TaxonRank | None:
    """Most-specific shared ancestor rank between two taxa.

    Inputs are ``(taxon_id, rank_str, parents_json)`` triples where
    ``parents_json`` is ordered root → immediate parent (Taxon.parents_json layout).

    The taxon itself counts as part of its own ancestor chain — passing the
    same taxon twice returns that taxon's rank. Returns ``None`` when the two
    chains share no ancestor at a real taxonomic rank.

    ``TaxonRank.UNKNOWN`` is excluded from the candidate set even though it
    sorts after SPECIES in OrderedEnum definition order — it isn't a real
    taxonomic rank and treating it as deeper-than-ORDER produces false
    under-order agreements when an UNKNOWN ancestor happens to be shared.
    """
    chain_a = [(p["id"], TaxonRank(p["rank"])) for p in a[2]] + [(a[0], TaxonRank(a[1]))]
    chain_b_ids = {p["id"] for p in b[2]} | {b[0]}

    deepest: TaxonRank | None = None
    for tid, rank in chain_a:
        if rank == TaxonRank.UNKNOWN:
            continue
        if tid in chain_b_ids:
            if deepest is None or rank > deepest:
                deepest = rank
    return deepest


# z-score for a 95% two-sided confidence interval (Wilson score).
WILSON_Z_95 = 1.959963984540054


def wilson_interval(successes: int, total: int, z: float = WILSON_Z_95) -> tuple[float, float] | None:
    """Wilson score confidence interval for a binomial proportion.

    Returns ``(low, high)`` bounded to ``[0, 1]`` (rounded to 4 dp), or
    ``None`` when ``total`` is 0. Defaults to a 95% interval.

    The Wilson score interval is used instead of the normal approximation
    because the verified set is often tiny (single-digit counts), where the
    normal approximation produces bounds outside [0, 1] and understates the
    uncertainty. Wilson stays well-behaved at small n and at proportions
    near 0 or 1.
    """
    if total <= 0:
        return None
    phat = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    center = (phat + z2 / (2 * total)) / denom
    margin = (z / denom) * math.sqrt(phat * (1 - phat) / total + z2 / (4 * total * total))
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return (round(low, 4), round(high, 4))


def cohens_kappa(pairs: list[tuple[int, int]]) -> float | None:
    """Cohen's kappa for exact-taxon agreement between human and model.

    ``pairs`` is one ``(human_taxon_id, model_taxon_id)`` per occurrence that
    both a human and the model assigned a taxon to. Returns kappa rounded to
    4 dp in ``[-1, 1]`` (negative = worse than chance), or ``None`` when
    there are no pairs or expected agreement is 1.0 (kappa undefined — a
    single category leaves no chance-agreement to correct for).

    Plain agreement rate rewards luck: in a project dominated by one common
    species, human and model agree most of the time just by both naming the
    common one. Kappa subtracts that chance agreement, so it answers "how
    much better than guessing is the model" rather than "how often do they
    happen to match".
    """
    n = len(pairs)
    if n == 0:
        return None
    observed_agree = sum(1 for h, m in pairs if h == m) / n
    human_counts: collections.Counter = collections.Counter(h for h, _ in pairs)
    model_counts: collections.Counter = collections.Counter(m for _, m in pairs)
    expected_agree = sum(
        (human_counts[taxon_id] / n) * (model_counts[taxon_id] / n)
        for taxon_id in set(human_counts) | set(model_counts)
    )
    if expected_agree >= 1.0:
        return None
    return round((observed_agree - expected_agree) / (1 - expected_agree), 4)


def _detections_prefetch(*, ordering: tuple[str, ...], with_source_image: bool) -> Prefetch:
    from ami.main.models import Classification, Detection

    qs = Detection.objects.prefetch_related(
        Prefetch(
            "classifications",
            queryset=Classification.objects.select_related("taxon", "algorithm"),
        )
    ).order_by(*ordering)
    if with_source_image:
        qs = qs.select_related("source_image")
    return Prefetch("detections", queryset=qs)


def prefetch_detections_for_list() -> Prefetch:
    """Detections + nested classifications, ordered for stable list image galleries."""
    return _detections_prefetch(ordering=("frame_num", "timestamp"), with_source_image=False)


def prefetch_detections_for_detail() -> Prefetch:
    """Detections + nested classifications + source_image, ordered most-recent-first.

    Detail responses serialize each detection via `DetectionNestedSerializer`,
    which dereferences `source_image` (as `capture`).
    """
    return _detections_prefetch(ordering=("-timestamp",), with_source_image=True)


def _require_prefetch(occurrence: Occurrence, *relations: str) -> None:
    """Raise if any required top-level relation is missing from the prefetch cache.

    Only checks top-level relations; nested prefetch (e.g. `detections__classifications`)
    is required by callers but not enforced here. Use the list/detail factories above
    to keep the pairing correct. Tighter depth-checking is deferred to django-zen-queries
    (#1271 follow-up).
    """
    cache = getattr(occurrence, "_prefetched_objects_cache", {})
    missing = [r for r in relations if r not in cache]
    if missing:
        raise RuntimeError(
            f"Occurrence {occurrence.pk} is missing prefetched relations {missing!r}. "
            "Apply OccurrenceQuerySet.with_list_prefetches() / with_detail_prefetches() / "
            "with_identifications() in the viewset's get_queryset()."
        )


def best_prediction_from_prefetch(occurrence: Occurrence) -> Classification | None:
    """Pick the best machine prediction from a prefetched occurrence in Python.

    Mirrors `Occurrence.best_prediction` (per-algorithm max-score, then `-terminal, -score`).
    Skips `score=None` to match SQL semantics of `score__in=Subquery(...)`.

    Strict: requires `detections` (and each detection's `classifications`) prefetched.
    """
    _require_prefetch(occurrence, "detections")
    classifications = [
        c for det in occurrence.detections.all() for c in det.classifications.all() if c.score is not None
    ]
    if not classifications:
        return None

    max_score_per_algo: dict[object, float] = {}
    for c in classifications:
        existing = max_score_per_algo.get(c.algorithm_id)
        if existing is None or c.score > existing:
            max_score_per_algo[c.algorithm_id] = c.score

    candidates = [c for c in classifications if c.score == max_score_per_algo[c.algorithm_id]]
    candidates.sort(
        key=lambda c: (
            0 if getattr(c, "terminal", False) else 1,
            -c.score,
            -c.pk,
        )
    )
    return candidates[0]


def best_identification_from_prefetch(occurrence: Occurrence) -> Identification | None:
    """Pick the most recent non-withdrawn identification from prefetched data.

    Mirrors `Occurrence.best_identification` (BEST_IDENTIFICATION_ORDER = -created_at, -pk).

    Strict: requires `identifications` prefetched (via `OccurrenceQuerySet.with_identifications()`).
    """
    _require_prefetch(occurrence, "identifications")
    best: Identification | None = None
    best_key: tuple[bool, object, int] | None = None
    for ident in occurrence.identifications.all():
        if ident.withdrawn:
            continue
        ident_key: tuple[bool, object, int] = (ident.created_at is not None, ident.created_at, ident.pk)
        if best_key is None or ident_key > best_key:
            best = ident
            best_key = ident_key
    return best


def detection_image_urls_from_prefetch(occurrence: Occurrence, limit: int | None = None) -> list[str]:
    """Return media URLs for the prefetched detections (filtering out `path=None`).

    Strict: requires `detections` prefetched. Pass `limit` to bound output.
    """
    _require_prefetch(occurrence, "detections")

    from ami.main.models import get_media_url

    detections = [det for det in occurrence.detections.all() if det.path]
    if limit is not None:
        detections = detections[:limit]
    return [get_media_url(det.path) for det in detections]


def model_agreement_for_project(
    queryset: QuerySet[Occurrence],
    coarsest_rank: TaxonRank | None = None,
) -> dict:
    """Verified / agreement stats over a pre-filtered Occurrence queryset.

    The queryset MUST already be filtered to the project + user-supplied
    filters (caller wires apply_default_filters + OccurrenceFilter). This
    function adds the annotations it needs and returns a dict matching
    ModelAgreementSerializer's field set (without project_id — the view
    layer adds that).

    "Verified" means the occurrence has at least one non-withdrawn
    Identification. "Model prediction" means the Classification chosen by
    BEST_MACHINE_PREDICTION_ORDER. "Any-rank" agreement means the user's
    taxon and the model's prediction share an ancestor at any real rank
    (UNKNOWN excluded) — exact matches included. The upstream filter (e.g.
    a Lepidoptera include list) is what bounds the meaningful scope, not
    a hardcoded rank threshold in this function.

    When ``coarsest_rank`` is supplied, additionally compute "coarser-rank"
    agreement: the LCA must be at ``coarsest_rank`` or deeper (e.g. passing
    FAMILY only counts LCAs at FAMILY, GENUS, or SPECIES). Exact matches
    always count regardless of rank.

    Performance: the heavy work — correlated subqueries over Identification
    and Classification — is scoped to the verified set, which is typically
    a tiny fraction of total occurrences. Computing those subqueries over
    the full filtered queryset would do 99% wasted work picking the "best
    user identification" for occurrences that have none.

      Step 1: total_occurrences = SQL Count(*).
      Step 2: Fetch the verified set with (pk, best_user_taxon_id,
              best_machine_prediction_taxon_id). Both correlated subqueries
              evaluate only on verified rows.
      Step 3: Bucket counts in Python (set is small).
      Step 4: Dedupe disagreement to distinct (user, machine) pairs and run
              one LCA per pair.

    Bench against project 18 (43,149 occurrences, 45 verified): ~80ms cold.
    """
    from ami.main.models import BEST_IDENTIFICATION_ORDER, Identification, Taxon

    # Default filters can join Identification (verified_by_me) and Taxon
    # parents_json (taxa_list_id) which inflates row count if not deduped.
    # Dedupe up front so total + verified counts share one canonical set.
    queryset = queryset.distinct()
    total = queryset.count()

    best_user_ident = Identification.objects.filter(occurrence=OuterRef("pk"), withdrawn=False).order_by(
        *BEST_IDENTIFICATION_ORDER
    )

    verified_rows = list(
        queryset.filter(identifications__withdrawn=False)
        .distinct()
        .with_best_machine_prediction()  # type: ignore[attr-defined]
        .annotate(best_user_taxon_id=Subquery(best_user_ident.values("taxon_id")[:1]))
        .values("pk", "best_machine_prediction_taxon_id", "best_user_taxon_id")
    )

    verified = len(verified_rows)
    no_prediction = sum(1 for r in verified_rows if r["best_machine_prediction_taxon_id"] is None)
    verified_with_pred = verified - no_prediction
    agreed_exact = sum(
        1
        for r in verified_rows
        if r["best_machine_prediction_taxon_id"] is not None
        and r["best_user_taxon_id"] == r["best_machine_prediction_taxon_id"]
    )

    # Dedupe disagreement pairs so each (user_taxon, machine_taxon) LCA runs once.
    pair_counts: collections.Counter = collections.Counter()
    for r in verified_rows:
        m_id = r["best_machine_prediction_taxon_id"]
        u_id = r["best_user_taxon_id"]
        if m_id is None or u_id is None or u_id == m_id:
            continue
        pair_counts[(u_id, m_id)] += 1

    needed_taxa_ids: set[int] = set()
    for u_id, m_id in pair_counts:
        needed_taxa_ids.add(u_id)
        needed_taxa_ids.add(m_id)

    taxa_by_id: dict[int, TaxonTuple] = {}
    if needed_taxa_ids:
        for t in Taxon.objects.filter(pk__in=needed_taxa_ids):
            parents = [
                {"id": p.id, "rank": p.rank.name if hasattr(p.rank, "name") else p.rank} for p in t.parents_json
            ]
            taxa_by_id[t.pk] = (t.pk, t.rank, parents)

    any_rank_disagreement_count = 0
    coarser_rank_disagreement_count = 0
    for (u_id, m_id), count in pair_counts.items():
        u = taxa_by_id.get(u_id)
        m = taxa_by_id.get(m_id)
        if not u or not m:
            continue
        lca = lca_rank_between(u, m)
        if lca is None:
            continue
        any_rank_disagreement_count += count
        if coarsest_rank is not None and lca >= coarsest_rank:
            coarser_rank_disagreement_count += count

    agreed_any_rank = agreed_exact + any_rank_disagreement_count
    agreed_coarser_rank = agreed_exact + coarser_rank_disagreement_count

    # Extra stats over the same verified_rows already in memory — no extra query.
    # Wilson 95% CI conveys how shaky each rate is at small n; Cohen's kappa
    # (exact-taxon) discounts the agreement you'd get by chance.
    exact_ci = wilson_interval(agreed_exact, verified_with_pred)
    any_rank_ci = wilson_interval(agreed_any_rank, verified_with_pred)
    both_present_pairs = [
        (r["best_user_taxon_id"], r["best_machine_prediction_taxon_id"])
        for r in verified_rows
        if r["best_user_taxon_id"] is not None and r["best_machine_prediction_taxon_id"] is not None
    ]
    kappa = cohens_kappa(both_present_pairs)

    def _pct(num: int, denom: int) -> float:
        return round(num / denom, 4) if denom else 0.0

    payload: dict = {
        "total_occurrences": total,
        "verified_count": verified,
        "verified_pct": _pct(verified, total),
        "verified_with_prediction_count": verified_with_pred,
        "no_prediction_count": no_prediction,
        "agreed_exact_count": agreed_exact,
        "agreed_exact_pct": _pct(agreed_exact, verified_with_pred),
        "agreed_exact_ci_low": exact_ci[0] if exact_ci else None,
        "agreed_exact_ci_high": exact_ci[1] if exact_ci else None,
        "agreed_any_rank_count": agreed_any_rank,
        "agreed_any_rank_pct": _pct(agreed_any_rank, verified_with_pred),
        "agreed_any_rank_ci_low": any_rank_ci[0] if any_rank_ci else None,
        "agreed_any_rank_ci_high": any_rank_ci[1] if any_rank_ci else None,
        "cohens_kappa": kappa,
        "agreement_coarsest_rank": coarsest_rank.name if coarsest_rank is not None else None,
        "agreed_coarser_rank_count": agreed_coarser_rank if coarsest_rank is not None else None,
        "agreed_coarser_rank_pct": (
            _pct(agreed_coarser_rank, verified_with_pred) if coarsest_rank is not None else None
        ),
    }
    return payload


def top_identifiers_for_project(project: Project) -> QuerySet[User]:
    """Project users ranked by distinct occurrences they identified.

    Counts distinct occurrences, not raw Identification rows: a user revising
    their own ID on the same occurrence is one occurrence-identification, not two.

    Always filters `identification_count >= 1` so anonymous / empty calls never
    leak the full project user list. **Non-configurable** — callers (paginator,
    list slicing) get to choose how many rows to return, but never which rows.
    """
    return (
        User.objects.filter(identifications__occurrence__project=project)
        .annotate(
            identification_count=Count(
                "identifications__occurrence",
                filter=Q(identifications__occurrence__project=project),
                distinct=True,
            )
        )
        .filter(identification_count__gt=0)
        .order_by("-identification_count")
    )
