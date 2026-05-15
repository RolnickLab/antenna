"""
Reusable Prefetch factories and aggregate queries for Occurrence rendering.

The serializer trusts the prefetch contract — the viewset is the single place
that wires it up. Don't gate serializer methods on `_prefetched_objects_cache`
membership; require the prefetch.

Tracking issue: https://github.com/RolnickLab/antenna/issues/1271
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Count, F, OuterRef, Prefetch, Q, QuerySet, Subquery

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


def model_agreement_for_project(queryset: QuerySet[Occurrence]) -> dict:
    """Verified / agreement stats over a pre-filtered Occurrence queryset.

    The queryset MUST already be filtered to the project + user-supplied
    filters (caller wires apply_default_filters + OccurrenceFilter). This
    function adds the annotations it needs and returns a dict matching
    ModelAgreementSerializer's field set (without project_id — the view
    layer adds that).

    "Verified" means the occurrence has at least one non-withdrawn
    Identification. "Model prediction" means the Classification chosen by
    BEST_MACHINE_PREDICTION_ORDER. "Under-order" agreement means the user's
    taxon and the model's prediction share an ancestor at rank >= ORDER
    (inclusive of ORDER itself).

    Aggregation is SQL-side. Only the disagreement set (occurrences where
    user and machine disagree at SPECIES) is materialized in Python, and
    even then it's deduplicated to distinct (user_taxon, machine_taxon)
    pairs so LCA runs once per pair, not once per occurrence.
    """
    from ami.main.models import BEST_IDENTIFICATION_ORDER, Identification, Taxon

    best_user_ident = Identification.objects.filter(occurrence=OuterRef("pk"), withdrawn=False).order_by(
        *BEST_IDENTIFICATION_ORDER
    )

    qs = queryset.with_best_machine_prediction().annotate(  # type: ignore[attr-defined]
        best_user_taxon_id=Subquery(best_user_ident.values("taxon_id")[:1]),
    )

    verified_q = Q(best_user_taxon_id__isnull=False)
    has_pred_q = Q(best_machine_prediction_taxon_id__isnull=False)
    exact_q = verified_q & has_pred_q & Q(best_user_taxon_id=F("best_machine_prediction_taxon_id"))

    aggregates = qs.aggregate(
        total_occurrences=Count("pk"),
        verified_count=Count("pk", filter=verified_q),
        verified_with_prediction_count=Count("pk", filter=verified_q & has_pred_q),
        no_prediction_count=Count("pk", filter=verified_q & ~has_pred_q),
        agreed_exact_count=Count("pk", filter=exact_q),
    )

    # Under-order: only the disagreement set hits Python, grouped by distinct
    # (user_taxon, machine_taxon) pair so each pair's LCA is computed once.
    disagreement_pairs = (
        qs.filter(verified_q & has_pred_q)
        .exclude(best_user_taxon_id=F("best_machine_prediction_taxon_id"))
        .values("best_user_taxon_id", "best_machine_prediction_taxon_id")
        .annotate(occurrence_count=Count("pk"))
    )

    pairs = list(disagreement_pairs)
    needed_taxa_ids = {p["best_user_taxon_id"] for p in pairs} | {p["best_machine_prediction_taxon_id"] for p in pairs}

    taxa_by_id: dict[int, TaxonTuple] = {}
    if needed_taxa_ids:
        for t in Taxon.objects.filter(pk__in=needed_taxa_ids):
            parents = [
                {"id": p.id, "rank": p.rank.name if hasattr(p.rank, "name") else p.rank} for p in t.parents_json
            ]
            taxa_by_id[t.pk] = (t.pk, t.rank, parents)

    under_order_disagreement_count = 0
    for pair in pairs:
        u = taxa_by_id.get(pair["best_user_taxon_id"])
        m = taxa_by_id.get(pair["best_machine_prediction_taxon_id"])
        if not u or not m:
            continue
        lca = lca_rank_between(u, m)
        if lca is not None and lca >= TaxonRank.ORDER:
            under_order_disagreement_count += pair["occurrence_count"]

    agreed_exact = aggregates["agreed_exact_count"]
    agreed_under_order = agreed_exact + under_order_disagreement_count
    total = aggregates["total_occurrences"]
    verified = aggregates["verified_count"]
    verified_with_pred = aggregates["verified_with_prediction_count"]

    def _pct(num: int, denom: int) -> float:
        return round(num / denom, 4) if denom else 0.0

    return {
        "total_occurrences": total,
        "verified_count": verified,
        "verified_pct": _pct(verified, total),
        "verified_with_prediction_count": verified_with_pred,
        "no_prediction_count": aggregates["no_prediction_count"],
        "agreed_exact_count": agreed_exact,
        "agreed_exact_pct": _pct(agreed_exact, verified_with_pred),
        "agreed_under_order_count": agreed_under_order,
        "agreed_under_order_pct": _pct(agreed_under_order, verified_with_pred),
    }


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
