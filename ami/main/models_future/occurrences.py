"""
The Occurrence model and its manager/queryset.
"""

from __future__ import annotations

import collections
import datetime
import functools
import logging
from typing import TYPE_CHECKING, Final, final

from django.apps import apps
from django.db import models
from django.db.models import Count, Exists, OuterRef, Prefetch, Q, QuerySet, Subquery
from rest_framework.request import Request

import ami.utils.dates
from ami.base.models import BaseModel, BaseQuerySet
from ami.main.models_future.enums import TaxonRank
from ami.main.models_future.filters import (
    build_occurrence_default_filters_q,
    build_occurrence_score_threshold_q,
    build_taxa_recursive_filter_q,
)
from ami.users.models import User
from ami.utils.requests import get_apply_default_filters_flag, get_default_classification_threshold
from ami.utils.stats import cohens_kappa, wilson_interval

if TYPE_CHECKING:
    from ami.main.models import Classification, Detection, Identification, Project, SourceImage, Taxon

TaxonTuple = tuple[int, str, list[dict]]

logger = logging.getLogger(__name__)

# Ordering for "best machine prediction" selection used by
# OccurrenceQuerySet.with_best_machine_prediction(). Terminal classifications win
# over non-terminal, then highest score, with pk as the deterministic tiebreaker.
BEST_MACHINE_PREDICTION_ORDER: Final = ("-terminal", "-score", "-pk")

# Ordering for "best identification" selection used by Occurrence.best_identification,
# OccurrenceQuerySet.with_verification_info(), and best_identification_from_prefetch().
# Most recent non-withdrawn identification wins, with pk as the deterministic tiebreaker.
BEST_IDENTIFICATION_ORDER: Final = ("-created_at", "-pk")


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
    # We need to do a function level import here to avoid a circular import,
    # since ami.main.models imports this module.
    from ami.main.models import Classification, Detection

    qs = Detection.objects.prefetch_related(
        Prefetch(
            "classifications",
            # applied_to__algorithm: post-processed classifications (class masking,
            # rank rollup) serialize their provenance parent; pull it here so the
            # nested applied_to render doesn't issue a query per classification.
            queryset=Classification.objects.select_related("taxon", "algorithm", "applied_to__algorithm"),
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
    # String to avoid circular import with ami.main.models.
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
    # String to avoid circular import with ami.main.models.
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
    # String to avoid circular import with ami.main.models.
    _require_prefetch(occurrence, "detections")

    # We need to do a function level import here to avoid a circular import,
    # since ami.main.models imports this module.
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
    # We need to do a function level import here to avoid a circular import,
    # since ami.main.models imports this module.
    from ami.main.models import Identification, Taxon

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
    # The agreement cohort needs BOTH a machine prediction and a human taxon to
    # compare. Identification.taxon is nullable (comment-only verifications), so a
    # verified row can have a prediction but no human label — it can neither agree
    # nor disagree and must be excluded from the denominator, not just the numerator.
    no_user_taxon = sum(
        1
        for r in verified_rows
        if r["best_machine_prediction_taxon_id"] is not None and r["best_user_taxon_id"] is None
    )
    comparable = verified_with_pred - no_user_taxon
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
    exact_ci = wilson_interval(agreed_exact, comparable)
    any_rank_ci = wilson_interval(agreed_any_rank, comparable)
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
        "verified_without_taxon_count": no_user_taxon,
        "comparable_count": comparable,
        "agreed_exact_count": agreed_exact,
        "agreed_exact_pct": _pct(agreed_exact, comparable),
        "agreed_exact_ci_low": exact_ci[0] if exact_ci else None,
        "agreed_exact_ci_high": exact_ci[1] if exact_ci else None,
        "agreed_any_rank_count": agreed_any_rank,
        "agreed_any_rank_pct": _pct(agreed_any_rank, comparable),
        "agreed_any_rank_ci_low": any_rank_ci[0] if any_rank_ci else None,
        "agreed_any_rank_ci_high": any_rank_ci[1] if any_rank_ci else None,
        "cohens_kappa": kappa,
        "agreement_coarsest_rank": coarsest_rank.name if coarsest_rank is not None else None,
        "agreed_coarser_rank_count": agreed_coarser_rank if coarsest_rank is not None else None,
        "agreed_coarser_rank_pct": (_pct(agreed_coarser_rank, comparable) if coarsest_rank is not None else None),
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


class OccurrenceQuerySet(BaseQuerySet):
    def valid(self):
        """
        Occurrences fit to surface in API responses: at least one real detection AND
        a determination set.

        Excludes:
          - Occurrences with no detections at all (empty occurrences)
          - Occurrences whose only detections are null-marker sentinels (Issue #1310:
            field bug created phantom occurrences with no real bounding box backing
            them)
          - Occurrences with determination__isnull=True (no taxonomic identification,
            same field bug shape)
        """
        # We need to do a function level import here to avoid a circular import,
        # since ami.main.models imports this module.
        from ami.main.models import Detection

        has_valid_detection = Exists(Detection.objects.valid().filter(occurrence_id=OuterRef("pk")))
        return self.filter(has_valid_detection).exclude(determination__isnull=True)

    def with_detections_count(self):
        return self.annotate(detections_count=models.Count("detections", distinct=True))

    def _processed_by_algorithm_q(self, algorithm_ids) -> Exists:
        """Subquery matching occurrences with any result from the given algorithms —
        a detection made by one (detectors) or a classification from one (classifiers
        and post-processing algorithms such as class masking or a size filter)."""
        # We need to do a function level import here to avoid a circular import,
        # since ami.main.models imports this module.
        from ami.main.models import Detection

        return Exists(
            Detection.objects.filter(occurrence_id=OuterRef("pk")).filter(
                models.Q(detection_algorithm__in=algorithm_ids)
                | models.Q(classifications__algorithm__in=algorithm_ids)
            )
        )

    def processed_by_algorithm(self, algorithm_ids) -> OccurrenceQuerySet:
        """Occurrences with at least one result from the given algorithms.

        Matches detectors through Detection.detection_algorithm and classifiers or
        post-processing algorithms through their classifications, so every algorithm
        listed by ``Algorithm.objects.used_in_project()`` can match here. The EXISTS
        form returns each occurrence once; a join through
        ``detections__classifications`` returns one row per matching result, which
        inflates pagination counts and duplicates rows across pages.
        """
        return self.filter(self._processed_by_algorithm_q(algorithm_ids))

    def not_processed_by_algorithm(self, algorithm_ids) -> OccurrenceQuerySet:
        """Occurrences with no result from any of the given algorithms."""
        return self.exclude(self._processed_by_algorithm_q(algorithm_ids))

    def created_or_updated_by_job(self, job_id: int) -> OccurrenceQuerySet:
        """Occurrences created or updated by the given job.

        An occurrence matches when the job created one of its detections, a classification
        on one of them, or an algorithm result for it, so several jobs can match the same occurrence.

        Identifications are not matched: people make them, not jobs. EXISTS subqueries return
        each occurrence once, where a join would return one row per matching result.
        """
        # We need to do a function level import here to avoid a circular import,
        # since ami.main.models imports this module.
        from ami.main.models import Classification, Detection

        AlgorithmResult = apps.get_model("ml", "AlgorithmResult")
        return self.filter(
            Exists(Detection.objects.filter(occurrence=OuterRef("pk"), job_id=job_id))
            | Exists(Classification.objects.filter(detection__occurrence=OuterRef("pk"), job_id=job_id))
            | Exists(AlgorithmResult.objects.filter(occurrence=OuterRef("pk"), job_id=job_id))
        )

    def with_timestamps(self):
        """
        These are timestamps used for filtering and ordering in the UI.
        """
        return self.annotate(
            first_appearance_timestamp=models.Min("detections__timestamp"),
            last_appearance_timestamp=models.Max("detections__timestamp"),
            first_appearance_time=models.Min("detections__timestamp__time"),
            duration=models.ExpressionWrapper(
                models.F("last_appearance_timestamp") - models.F("first_appearance_timestamp"),
                output_field=models.DurationField(),
            ),
        )

    def with_identifications(self):
        return self.prefetch_related(
            "identifications",
            "identifications__taxon",
            "identifications__user",
        )

    def with_list_prefetches(self):
        """Add prefetches the list serializer needs (detection paths, classifications)."""
        return self.prefetch_related(prefetch_detections_for_list())

    def with_detail_prefetches(self):
        """Add prefetches the detail serializer needs (detections + source_image + classifications)."""
        return self.prefetch_related(prefetch_detections_for_detail())

    def with_best_detection(self):
        """
        Annotate the queryset with fields from the best detection.
        The best detection is the one with the highest classification score.

        Adds the following annotations:
        - best_detection_id: The primary key of the best detection
        - best_detection_path: The path to the detection image
        - best_detection_bbox: The bounding box of the detection as a list [x1, y1, x2, y2]
        - best_detection_capture_path: The path of the source capture image
        - best_detection_capture_public_base_url: The public base URL of the source capture image

        ``best_detection_id`` picks the same detection as ``best_detection_path`` (identical
        ordering), so callers that need both an id and the image can rely on them referring
        to one detection rather than re-deriving the pick with a second, drift-prone subquery.
        """
        # One ordering for every field so they all describe the same detection. nulls_last:
        # a detection with no classification would otherwise sort first under DESC and be
        # picked as "best"; .valid() keeps null-marker rows out.

        # We need to do a function level import here to avoid a circular import,
        # since ami.main.models imports this module.
        from ami.main.models import Detection

        best_detections = (
            Detection.objects.valid()  # type: ignore[union-attr]
            .filter(occurrence=OuterRef("pk"))
            .order_by(models.F("classifications__score").desc(nulls_last=True), "id")
        )
        best_detection_id_subquery = best_detections.values("id")[:1]
        best_detection_path_subquery = best_detections.values("path")[:1]
        best_detection_bbox_subquery = best_detections.values("bbox")[:1]
        best_detection_capture_path_subquery = best_detections.values("source_image__path")[:1]
        best_detection_capture_public_base_url_subquery = best_detections.values("source_image__public_base_url")[:1]

        return self.annotate(
            best_detection_id=models.Subquery(best_detection_id_subquery),
            best_detection_path=models.Subquery(best_detection_path_subquery),
            best_detection_bbox=models.Subquery(best_detection_bbox_subquery),
            best_detection_capture_path=models.Subquery(best_detection_capture_path_subquery),
            best_detection_capture_public_base_url=models.Subquery(best_detection_capture_public_base_url_subquery),
        )

    def with_best_machine_prediction(self):
        """
        Annotate the queryset with fields from the best machine prediction.

        Uses BEST_MACHINE_PREDICTION_ORDER to pick the winner: terminal classifications
        first, then highest score, with pk as the deterministic tiebreaker.

        Adds the following annotations:
        - best_machine_prediction_name: The taxon name of the best prediction
        - best_machine_prediction_score: The confidence score
        - best_machine_prediction_algorithm: The algorithm name
        - best_machine_prediction_taxon_id: The taxon ID (for determination_matches comparison)
        """
        # We need to do a function level import here to avoid a circular import,
        # since ami.main.models imports this module.
        from ami.main.models import Classification

        best_prediction_subquery = Classification.objects.filter(detection__occurrence=OuterRef("pk")).order_by(
            *BEST_MACHINE_PREDICTION_ORDER
        )

        return self.annotate(
            best_machine_prediction_name=models.Subquery(best_prediction_subquery.values("taxon__name")[:1]),
            best_machine_prediction_score=models.Subquery(best_prediction_subquery.values("score")[:1]),
            best_machine_prediction_algorithm=models.Subquery(best_prediction_subquery.values("algorithm__name")[:1]),
            best_machine_prediction_taxon_id=models.Subquery(best_prediction_subquery.values("taxon_id")[:1]),
        )

    def with_verification_info(self):
        """
        Annotate the queryset with verification/identification fields.

        Adds the following annotations:
        - verified_by_name: The name of the user who made the best identification
        - participant_count: The count of distinct users who made non-withdrawn identifications
        - agreed_with_algorithm_name: The algorithm name the identifier agreed with
        - agreed_with_user_email: The email of the prior identifier the best identification agreed with
        """
        # We need to do a function level import here to avoid a circular import,
        # since ami.main.models imports this module.
        from ami.main.models import Identification

        best_identification_subquery = Identification.objects.filter(
            occurrence=OuterRef("pk"), withdrawn=False
        ).order_by(*BEST_IDENTIFICATION_ORDER)

        return self.annotate(
            verified_by_name=models.Subquery(best_identification_subquery.values("user__name")[:1]),
            participant_count=models.Count(
                "identifications__user",
                filter=Q(identifications__withdrawn=False),
                distinct=True,
            ),
            agreed_with_algorithm_name=models.Subquery(
                best_identification_subquery.values("agreed_with_prediction__algorithm__name")[:1]
            ),
            agreed_with_user_email=models.Subquery(
                best_identification_subquery.values("agreed_with_identification__user__email")[:1]
            ),
        )

    def unique_taxa(self, project: Project | None = None):
        qs = self
        if project:
            qs = self.filter(project=project)
        qs = (
            qs.filter(determination__isnull=False, event__isnull=False)
            .order_by("determination_id")
            .distinct("determination_id")
        )
        return qs

    def filter_by_score_threshold(self, project: Project | None = None, request: Request | None = None):
        """
        Filter occurrences by score threshold.

        This is a convenience method for applying only the score threshold filter.
        Respects the apply_defaults flag - if False, filtering is bypassed.
        """
        if project is None:
            return self

        # Check if default filters should be bypassed
        if get_apply_default_filters_flag(request) is False:
            return self

        score_threshold = get_default_classification_threshold(project, request)
        logger.debug(f"Filtering occurrences by determination score threshold of {score_threshold}")
        filter_q = build_occurrence_score_threshold_q(score_threshold, occurrence_accessor="")
        return self.filter(filter_q)

    def filter_by_project_default_taxa(self, project: Project | None = None, request: Request | None = None):
        """
        Filter occurrences by project's default include/exclude taxa lists.

        Respects the apply_defaults flag - if False, filtering is bypassed.
        """
        if project is None:
            return self

        # Check if default filters should be bypassed
        if get_apply_default_filters_flag(request) is False:
            return self

        qs = self

        # Apply taxa inclusion/exclusion filter
        include_taxa = project.default_filters_include_taxa.all()
        exclude_taxa = project.default_filters_exclude_taxa.all()
        taxa_q = build_taxa_recursive_filter_q(include_taxa, exclude_taxa, taxon_accessor="determination")
        if taxa_q:
            qs = qs.filter(taxa_q)

        return qs

    def apply_default_filters(self, project: Project | None = None, request: Request | None = None):
        """
        Apply all default filters to occurrences based on project settings.

        This is the standard method for filtering occurrences according to project defaults.
        It applies both score threshold and taxa filters in a single call.

        Args:
            project: The project whose default filters should be applied
            request: The request object (optional, used to check for apply_defaults=false)

        Returns:
            Filtered queryset with both score and taxa filters applied

        Example:
            # In a viewset
            qs = Occurrence.objects.apply_default_filters(project, self.request)

            # In a model method
            qs = Occurrence.objects.apply_default_filters(self.project, None)
        """
        if project is None:
            return self

        # Check if default filters should be bypassed entirely
        if get_apply_default_filters_flag(request) is False:
            return self

        # Use build_occurrence_default_filters_q to get the combined filter and apply it
        filter_q = build_occurrence_default_filters_q(project, request, occurrence_accessor="")
        return self.filter(filter_q)


class OccurrenceManager(models.Manager.from_queryset(OccurrenceQuerySet)):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "determination",
                "deployment",
                "project",
            )
        )


@final
class Occurrence(BaseModel):
    """An occurrence of a taxon, a sequence of one or more detections"""

    reference_type = "occurrence"
    reference_name_field = None

    # @TODO change Determination to a nested field with a Taxon, User, Identification, etc like the serializer
    # this could be a OneToOneField to a Determination model or a JSONField validated by a Pydantic model
    determination = models.ForeignKey("Taxon", on_delete=models.SET_NULL, null=True, related_name="occurrences")
    determination_score = models.FloatField(null=True, blank=True)

    event = models.ForeignKey("Event", on_delete=models.SET_NULL, null=True, related_name="occurrences")
    deployment = models.ForeignKey("Deployment", on_delete=models.SET_NULL, null=True, related_name="occurrences")
    project = models.ForeignKey("Project", on_delete=models.SET_NULL, null=True, related_name="occurrences")

    detections: models.QuerySet[Detection]
    identifications: models.QuerySet[Identification]

    objects = OccurrenceManager()

    def __str__(self) -> str:
        name = f"Occurrence #{self.pk}"
        if self.deployment:
            name += f" ({self.deployment.name})"
        if self.determination:
            name += f" ({self.determination.name})"
        return name

    def detections_count(self) -> int | None:
        # Annotations don't seem to work with nested serializers
        return self.detections.count()

    @functools.cached_property
    def first_appearance(self) -> SourceImage | None:
        # @TODO it appears we only need the first timestamp, that could be an annotated value
        first = self.detections.order_by("timestamp").select_related("source_image").first()
        if first:
            return first.source_image

    @functools.cached_property
    def last_appearance(self) -> SourceImage | None:
        # @TODO it appears we only need the last timestamp, that could be an annotated value
        last = self.detections.order_by("timestamp").select_related("source_image").last()
        if last:
            return last.source_image

    def first_appearance_timestamp(self) -> datetime.datetime | None:
        """
        Return the timestamp of the first appearance.
        ONLY if it has been added with a query annotation.
        """
        return None

    def first_appearance_time(self) -> datetime.time | None:
        """
        Return the time part only of the first appearance.
        ONLY if it has been added with a query annotation.
        """
        return None

    def last_appearance_timestamp(self) -> datetime.datetime | None:
        """
        Return the timestamp of the last appearance.
        ONLY if it has been added with a query annotation.
        """
        return None

    def duration(self) -> datetime.timedelta | None:
        first = self.first_appearance
        last = self.last_appearance
        if first and last and first.timestamp and last.timestamp:
            return last.timestamp - first.timestamp
        else:
            return None

    def duration_label(self) -> str | None:
        """
        If duration has been calculated by a query annotation, use that value
        otherwise call the duration() method to calculate it.
        """
        duration = self.duration() if callable(self.duration) else self.duration
        return ami.utils.dates.format_timedelta(duration)

    def detection_images(self, limit=None):
        # We need to do a function level import here to avoid a circular import,
        # since ami.main.models imports this module.
        from ami.main.models import Detection, get_media_url

        for path in (
            Detection.objects.filter(occurrence=self).exclude(path=None).values_list("path", flat=True)[:limit]
        ):
            yield get_media_url(path)

    @functools.cached_property
    def best_detection(self):
        # We need to do a function level import here to avoid a circular import,
        # since ami.main.models imports this module.
        from ami.main.models import Detection

        return Detection.objects.filter(occurrence=self).order_by("-classifications__score").first()

    @functools.cached_property
    def best_prediction(self):
        """
        Use the best prediction as the best identification if there are no human identifications.

        Uses the highest scoring classification (from any algorithm) as the best prediction.
        Considers terminal classifications first, then non-terminal ones.
        (Terminal classifications are the final classifications of a pipeline, non-terminal are intermediate models.)
        """
        return self.predictions().order_by("-terminal", "-score").first()

    @functools.cached_property
    def best_identification(self):
        """
        The most recent human identification is used as the best identification.

        @TODO this could use a confidence level chosen manually by the users/experts.
        """
        # We need to do a function level import here to avoid a circular import,
        # since ami.main.models imports this module.
        from ami.main.models import Identification

        return (
            Identification.objects.filter(occurrence=self, withdrawn=False)
            .order_by(*BEST_IDENTIFICATION_ORDER)
            .first()
        )

    def get_determination_score(self) -> float | None:
        if not self.determination:
            return None
        elif self.best_identification:
            return self.best_identification.score
        elif self.best_prediction:
            return self.best_prediction.score
        else:
            return None

    def predictions(self):
        """
        Retrieve the classification with the max score for each algorithm.
        select_related avoids per-row taxon/algorithm lazy loads when callers
        serialize the result (e.g. OccurrenceListSerializer.best_prediction).
        """
        # We need to do a function level import here to avoid a circular import,
        # since ami.main.models imports this module.
        from ami.main.models import Classification

        classifications = (
            Classification.objects.filter(detection__occurrence=self)
            .select_related("taxon", "algorithm")
            .filter(
                score__in=models.Subquery(
                    Classification.objects.filter(detection__occurrence=self)
                    .values("algorithm")
                    .annotate(max_score=models.Max("score"))
                    .values("max_score")
                )
            )
            .order_by("-created_at")
        )
        return classifications

    def context_url(self):
        detection = self.best_detection
        if detection and detection.source_image and detection.source_image.event:
            # @TODO this was a temporary hack. Use settings and reverse().
            return f"https://app.preview.insectai.org/sessions/{detection.source_image.event.pk}?capture={detection.source_image.pk}&occurrence={self.pk}"  # noqa E501
        else:
            return None

    def url(self):
        # @TODO this was a temporary hack. Use settings and reverse().
        return f"https://app.preview.insectai.org/occurrences/{self.pk}"

    def save(self, update_determination=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if update_determination:
            update_occurrence_determination(
                self,
                current_determination=self.determination,
                save=True,
            )

        if self.determination and not self.determination_score:
            # This may happen for legacy occurrences that were created
            # before the determination_score field was added
            # @TODO remove
            self.determination_score = self.get_determination_score()
            if not self.determination_score:
                logger.warning(f"Could not determine score for {self}")
            else:
                self.save(update_determination=False)

    class Meta:
        ordering = ["-determination_score"]
        indexes = [
            # Composite index for taxa queries filtered by project
            # Optimizes the taxa list query which executes correlated subqueries for each taxon
            # Pattern: WHERE determination_id=? AND project_id=? AND event_id IS NOT NULL AND determination_score>=?
            models.Index(
                fields=["determination_id", "project_id", "event_id", "determination_score"],
                name="occur_det_proj_evt_score",
            ),
            # Composite index for timestamp queries (last_detected)
            # Optimizes queries that join with detections table for timestamps
            # Pattern: WHERE determination_id=? AND project_id=? AND event_id IS NOT NULL
            models.Index(
                fields=["determination_id", "project_id", "event_id"],
                name="occur_det_proj_evt",
            ),
            # Supports sorting projects by their most recently updated occurrence
            # (see ProjectViewSet ordering "last_occurrence_updated_at").
            models.Index(fields=["project", "-updated_at"], name="occur_proj_updated_desc_idx"),
            # Backs the default occurrence list sort: per-project, ordered by
            # determination_score DESC (Meta.ordering). Without it the planner
            # sorts the whole project's occurrences per page (on-disk merge sort
            # on large projects). DESC = NULLS FIRST to match the ORM's ORDER BY.
            models.Index(fields=["project", "-determination_score"], name="occur_proj_score_desc_idx"),
        ]


def update_occurrence_determination(
    occurrence: Occurrence, current_determination: Taxon | None = None, save=True
) -> bool:
    """
    Update the determination of the occurrence based on the identifications & predictions.

    If there are identifications, set the determination to the latest identification.
    If there are no identifications, set the determination to the top prediction.

    The `current_determination` is the determination currently saved in the database.
    The `occurrence` object may already have a different un-saved determination set
    so it is necessary to retrieve the current determination from the database, but
    this can also be passed in as an argument to avoid an extra database query.

    @TODO Add tests for this important method!
    """
    needs_update = False

    # Invalidate the cached properties so they will be re-calculated
    if hasattr(occurrence, "best_identification"):
        del occurrence.best_identification
    if hasattr(occurrence, "best_prediction"):
        del occurrence.best_prediction
    if hasattr(occurrence, "best_identification"):
        del occurrence.best_identification

    current_determination = (
        current_determination
        or Occurrence.objects.select_related("determination")
        .values("determination")
        .get(pk=occurrence.pk)["determination"]
    )
    new_determination = None
    new_score = None

    top_identification = occurrence.best_identification
    if top_identification and top_identification.taxon and top_identification.taxon != current_determination:
        new_determination = top_identification.taxon
        new_score = top_identification.score
    elif not top_identification:
        top_prediction = occurrence.best_prediction
        if top_prediction and top_prediction.taxon and top_prediction.taxon != current_determination:
            new_determination = top_prediction.taxon
            new_score = top_prediction.score

    if new_determination and new_determination != current_determination:
        logger.debug(f"Changing det. of {occurrence} from {current_determination} to {new_determination}")
        occurrence.determination = new_determination
        needs_update = True

    if new_score and new_score != occurrence.determination_score:
        logger.debug(f"Changing det. score of {occurrence} from {occurrence.determination_score} to {new_score}")
        occurrence.determination_score = new_score
        needs_update = True

    if not needs_update:
        if logger.getEffectiveLevel() <= logging.DEBUG:
            all_predictions = occurrence.predictions()
            all_preds_print = ", ".join([str(p) for p in all_predictions])
            logger.debug(
                f"No update needed for determination of {occurrence}. Best prediction: {occurrence.best_prediction}. "
                f"All preds: {all_preds_print}"
            )

    if save and needs_update:
        occurrence.save(update_determination=False)

    return needs_update
