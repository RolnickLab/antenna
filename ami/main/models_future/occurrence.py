"""
Reusable Prefetch factories and aggregate queries for Occurrence rendering.

The serializer trusts the prefetch contract — the viewset is the single place
that wires it up. Don't gate serializer methods on `_prefetched_objects_cache`
membership; require the prefetch.

Tracking issue: https://github.com/RolnickLab/antenna/issues/1271
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Count, Prefetch, Q, QuerySet

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
    chains share no ancestor (e.g. one has an empty parents_json and the other
    doesn't include it).
    """
    chain_a = [(p["id"], TaxonRank(p["rank"])) for p in a[2]] + [(a[0], TaxonRank(a[1]))]
    chain_b_ids = {p["id"] for p in b[2]} | {b[0]}

    deepest: TaxonRank | None = None
    for tid, rank in chain_a:
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


def human_model_agreement_for_project(queryset: QuerySet[Occurrence]) -> dict:
    """Verified / agreement stats over a pre-filtered Occurrence queryset.

    The queryset MUST already be filtered to the project + user-supplied
    filters (caller wires apply_default_filters + OccurrenceFilter). This
    function adds the prefetches/annotations it needs and returns a dict
    matching HumanModelAgreementSerializer's field set (without project_id —
    the view layer adds that).

    "Verified" means the occurrence has at least one non-withdrawn
    Identification. "Model prediction" means the Classification chosen by
    BEST_MACHINE_PREDICTION_ORDER. "Under-order" agreement means the user's
    taxon and the model's prediction share an ancestor at rank >= ORDER
    (inclusive of ORDER itself).
    """
    from ami.main.models import Identification, Taxon

    qs = queryset.with_best_machine_prediction().prefetch_related(  # type: ignore[attr-defined]
        Prefetch(
            "identifications",
            queryset=Identification.objects.filter(withdrawn=False)
            .select_related("taxon")
            .order_by("-created_at", "-pk"),
            to_attr="_non_withdrawn_idents",
        )
    )

    occurrences = list(qs)

    needed_taxa_ids: set[int] = set()
    for occ in occurrences:
        machine_id = getattr(occ, "best_machine_prediction_taxon_id", None)
        if machine_id:
            needed_taxa_ids.add(machine_id)
        idents = getattr(occ, "_non_withdrawn_idents", [])
        if idents:
            needed_taxa_ids.add(idents[0].taxon_id)

    taxa_by_id: dict[int, TaxonTuple] = {}
    for t in Taxon.objects.filter(pk__in=needed_taxa_ids):
        parents = [{"id": p.id, "rank": p.rank.name if hasattr(p.rank, "name") else p.rank} for p in t.parents_json]
        taxa_by_id[t.pk] = (t.pk, t.rank, parents)

    total = len(occurrences)
    verified = 0
    agreed_exact = 0
    agreed_under_order = 0

    for occ in occurrences:
        idents = getattr(occ, "_non_withdrawn_idents", [])
        if not idents:
            continue
        verified += 1
        user_taxon_id = idents[0].taxon_id
        machine_taxon_id = getattr(occ, "best_machine_prediction_taxon_id", None)
        if not machine_taxon_id or not user_taxon_id:
            continue
        if user_taxon_id == machine_taxon_id:
            agreed_exact += 1
            agreed_under_order += 1
            continue
        user_tuple = taxa_by_id.get(user_taxon_id)
        machine_tuple = taxa_by_id.get(machine_taxon_id)
        if not user_tuple or not machine_tuple:
            continue
        lca = lca_rank_between(user_tuple, machine_tuple)
        if lca is not None and lca >= TaxonRank.ORDER:
            agreed_under_order += 1

    def _pct(num: int, denom: int) -> float:
        return round(num / denom, 4) if denom else 0.0

    return {
        "total_occurrences": total,
        "verified_count": verified,
        "verified_pct": _pct(verified, total),
        "agreed_exact_count": agreed_exact,
        "agreed_exact_pct": _pct(agreed_exact, verified),
        "agreed_under_order_count": agreed_under_order,
        "agreed_under_order_pct": _pct(agreed_under_order, verified),
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
