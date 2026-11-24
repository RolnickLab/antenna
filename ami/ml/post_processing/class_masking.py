import logging
import typing
from collections.abc import Callable

import numpy as np
import pydantic
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from ami.base.model_references import model_reference
from ami.main.models import Classification, Occurrence, SourceImageCollection, TaxaList
from ami.ml.models.algorithm import Algorithm, AlgorithmTaskType
from ami.ml.post_processing.base import BasePostProcessingTask
from ami.ml.results.schemas import DeterminationSnapshot
from ami.ml.results.writer import AlgorithmResultWriter
from ami.utils.query_cache import no_query_cache

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job

logger = logging.getLogger(__name__)

# The weight a class outside the taxa list gets when the config names none. It is above
# 0, so the default is a soft mask: such a class wins only when its probability is more
# than 100 times that of the best class in the list.
DEFAULT_OUT_OF_LIST_WEIGHT = 0.01
# Weights are rounded to this many decimals, so that each weight has one masking Algorithm.
WEIGHT_DECIMALS = 4
# The smallest weight above 0 that those decimals can hold.
SMALLEST_OUT_OF_LIST_WEIGHT = 10**-WEIGHT_DECIMALS


class ClassMaskingConfig(pydantic.BaseModel):
    # Scope: exactly one of these identifies which classifications to re-score. A
    # capture set is the bulk path; a single occurrence is the spot/dev path (fast
    # feedback while tuning a taxa list). This mirrors SmallSizeFilterConfig's
    # discriminated-scope shape — the shared pattern for per-occurrence triggers.
    source_image_collection_id: int | None = model_reference("capture_set", None, title="Capture set")
    occurrence_id: int | None = model_reference("occurrence", None, title="Occurrence")
    # The taxa list sorts the classifier's classes into three groups. A class whose
    # taxon is in the list keeps its score. A class whose taxon is outside the list is
    # down-weighted by ``out_of_list_weight``. A class with no resolvable taxon is
    # always removed, because it cannot become a determination.
    taxa_list_id: int = model_reference("taxa_list", ..., title="Species list")
    # The source classifier whose terminal classifications are re-scored.
    algorithm_id: int = model_reference("algorithm", ..., title="Classifier")
    # "Reweight" means renormalise; the class weight is ``out_of_list_weight``. When
    # True (default), the scores are renormalised to sum to 1 after the weight is
    # applied. When False, the classes in the list keep their original absolute scores,
    # which only describes a hard mask, so it needs a weight of 0.
    reweight: bool = pydantic.Field(True, title="Renormalised scores")
    # The prior weight of a class outside the list, against 1 for a class in the list.
    # 0 removes these classes (a hard mask). Above 0, a class outside the list still
    # wins when its probability is more than 1/weight times the best class in the list.
    # Declared after ``reweight`` because its validator reads that field.
    out_of_list_weight: float = pydantic.Field(
        DEFAULT_OUT_OF_LIST_WEIGHT, ge=0, lt=1, title="Weight for species outside the list"
    )

    # ``always=True`` runs the check on the default weight too, so ``reweight=False``
    # with the weight left out is reported instead of passing unchecked.
    @pydantic.validator("out_of_list_weight", always=True)
    def _usable_weight(cls, value: float, values: dict) -> float:
        # Compared before rounding: half the smallest weight and above would round up to
        # it, and the run would use up to twice the weight that was asked for.
        if 0 < value < SMALLEST_OUT_OF_LIST_WEIGHT:
            raise ValueError(f"Weights below {SMALLEST_OUT_OF_LIST_WEIGHT:g} are not supported; use 0 for a hard mask")
        rounded = round(value, WEIGHT_DECIMALS)
        if rounded >= 1:
            raise ValueError("The weight must be below 1; a weight of 1 changes nothing")
        if rounded > 0 and values.get("reweight") is False:
            raise ValueError("Scores without renormalisation need a hard mask: set the weight to 0")
        return rounded

    @pydantic.root_validator(skip_on_failure=True)
    def _exactly_one_scope(cls, values: dict) -> dict:
        scopes = [values.get("source_image_collection_id"), values.get("occurrence_id")]
        if sum(s is not None for s in scopes) != 1:
            raise ValueError("Provide exactly one of source_image_collection_id or occurrence_id")
        return values

    class Config:
        extra = "forbid"


class ClassMaskingResultData(DeterminationSnapshot):
    """Figures from the occurrence's winning detection: the one whose masked classification scores highest."""

    kind: typing.ClassVar[str] = "class_masking"
    value_field: typing.ClassVar[str | None] = "excluded_probability"

    # The classifier's probability outside the list, before the list was applied. It is
    # not an out-of-distribution score.
    excluded_probability: float
    # The share of the stored scores that is outside the list; 0 for a hard mask.
    excluded_probability_after: float | None = None
    # Where the class that wins after masking ranked before it; 1 means it was already the top.
    new_winner_original_rank: int | None = None
    # False when a species outside the list still won.
    winner_in_list: bool | None = None


def make_classifications_filtered_by_taxa_list(
    classifications: QuerySet[Classification],
    taxa_list: TaxaList,
    algorithm: Algorithm,
    new_algorithm: Algorithm,
    *,
    batch_size: int = 200,
    reweight: bool = True,
    out_of_list_weight: float = DEFAULT_OUT_OF_LIST_WEIGHT,
    task_logger: logging.Logger = logger,
    on_setup: Callable[[int], None] | None = None,
    on_batch: Callable[[dict], None] | None = None,
    job: "Job | None" = None,
) -> dict[str, int]:
    """Re-score ``classifications`` by down-weighting classes absent from ``taxa_list``.

    For each terminal classification produced by ``algorithm``, the classifier's
    softmax is recomputed from the logits and every class is multiplied by a prior
    weight: 1 when its taxon is in ``taxa_list``, ``out_of_list_weight`` when its taxon
    is outside the list, and 0 when it has no resolvable taxon. The result is
    renormalised to sum to 1, which equals a softmax of the logits plus the log of the
    weight. A new terminal classification (attributed to ``new_algorithm``, linked back
    via ``applied_to``) records the re-scored prediction. The original classification
    is demoted to non-terminal.

    A weight of 0 is a hard mask: no class outside the list can win. Above 0, a class
    outside the list still wins when its probability is more than ``1 / weight`` times
    that of the best class in the list. ``reweight=False`` skips the renormalisation, so
    the classes in the list keep their original absolute scores; it is only accepted
    with a weight of 0.

    The ``logits`` column is always read as logits. A row that stores probabilities
    there is not detected.

    Reads and commits in batches of ``batch_size`` so memory stays bounded and the
    job health-check reaper sees regular heartbeats. ``on_batch`` is called after
    every flush with running counters:
    ``{"classifications_checked": i, "classifications_total": total,
       "classifications_masked": masked_count, "occurrences_updated": n_changed}``.

    ``on_setup`` is called once with the number of classifications in scope, before
    the first row is processed, so a long run reports what it found up front.

    ``occurrences_updated`` counts only occurrences whose determination actually
    changed (not just any occurrence touched), matching the size-filter convention.

    New classifications record ``job`` as the run that wrote them.

    Every occurrence with a re-scored classification gets one algorithm result, written in
    the same transaction as the batch that changes it, and its new classifications point at
    that result (see ``AlgorithmResultWriter``). The result records, for the occurrence's winning
    detection, the probability outside the list before and after the weight was applied and
    whether the winner is in the list; the original top prediction is the classification the
    winning one replaced (``applied_to``).

    Returns final counters (checked / masked / occurrences updated) for stage metrics.
    """
    if batch_size <= 0:
        raise ValueError(f"batch_size must be positive, got {batch_size}")
    # ``ClassMaskingConfig`` reports these to users; the checks here cover direct callers.
    if not 0 <= out_of_list_weight < 1:
        raise ValueError(f"out_of_list_weight must be at least 0 and below 1, got {out_of_list_weight}")
    if out_of_list_weight > 0 and not reweight:
        raise ValueError("reweight=False needs a hard mask (out_of_list_weight=0)")

    taxa_in_list = set(taxa_list.taxa.all())

    # Resolve the scope to ids up front, then read one batch per query. Do not go back
    # to ``.iterator()``: the query cache reads an iterator to the end before yielding
    # its first row, so the first progress report waited on the whole scope and wide
    # runs were revoked as stalled (or killed for memory). See #1404.
    scope_ids = list(classifications.order_by().values_list("pk", flat=True))
    total = len(scope_ids)
    task_logger.info(f"Found {total} terminal classifications with scores to re-score.")
    if total == 0:
        task_logger.warning(
            "No terminal classifications from this classifier are in scope. Rows that an earlier "
            "class masking run re-scored are not re-scored again."
        )

    if not algorithm.category_map:
        raise ValueError(f"Algorithm {algorithm} does not have a category map.")
    category_map = algorithm.category_map

    # Resolve each category's taxon once, then give every class a prior weight: 1 when
    # its taxon is in the taxa list, ``out_of_list_weight`` when its taxon is outside
    # the list, and 0 when the map resolves no taxon for it. A class without a taxon
    # cannot become a determination, so it is removed at every weight, never kept.
    task_logger.info(f"Retrieving category map with Taxa instances for algorithm {algorithm}")
    category_map_with_taxa = category_map.with_taxa()
    index_to_taxon = {int(category["index"]): category["taxon"] for category in category_map_with_taxa}
    num_categories = len(category_map.labels)
    included_indices = [i for i in range(num_categories) if index_to_taxon.get(i) in taxa_in_list]

    if not included_indices:
        raise ValueError(
            f"Taxa list '{taxa_list.name}' excludes every class in algorithm '{algorithm.name}'s "
            "category map; there is nothing to keep."
        )

    in_list = np.zeros(num_categories, dtype=bool)
    in_list[included_indices] = True
    not_in_list = ~in_list
    has_taxon = np.array([index_to_taxon.get(i) is not None for i in range(num_categories)])
    prior = np.where(in_list, 1.0, np.where(has_taxon, out_of_list_weight, 0.0))

    outside_list_count = int((has_taxon & not_in_list).sum())
    task_logger.info(
        f"Category map has {num_categories} classes: {len(included_indices)} in the list, "
        f"{outside_list_count} outside the list (weight {out_of_list_weight:g}), "
        f"{num_categories - len(included_indices) - outside_list_count} with no taxon (removed); "
        f"{total} classifications to check"
    )

    classifications_to_demote: list[Classification] = []
    classifications_to_add: list[Classification] = []
    occurrences_to_update: set[Occurrence] = set()
    # Tracks occurrences whose determination actually changed across all batches.
    changed_occurrence_ids: set[int] = set()

    timestamp = timezone.now()
    masked_count = 0
    results = AlgorithmResultWriter(
        kind=ClassMaskingResultData.kind,
        algorithm=new_algorithm,
        job=job,
        timestamp=timestamp,
    )

    # Sizing the scope and expanding the category map both take time on a large
    # classifier, so report before touching a row.
    if on_setup is not None:
        on_setup(total)

    i = 0
    for start in range(0, total, batch_size):
        # ``scores`` is never read while masking and is as large as ``logits``. The
        # query cache is bypassed because each batch is read once, and caching it would
        # leave tens of megabytes per batch in Redis.
        with no_query_cache():
            batch = list(
                classifications.filter(pk__in=scope_ids[start : start + batch_size]).order_by().defer("scores")
            )

        for classification in batch:
            i += 1
            logits = classification.logits
            if not isinstance(logits, list) or not all(isinstance(x, (int, float)) for x in logits):
                raise ValueError(f"Logits for classification {classification.pk} are not a list of numbers: {logits}")
            elif len(logits) != num_categories:
                task_logger.warning(
                    f"Classification {classification.pk}: {len(logits)} logits "
                    f"!= {num_categories} categories; skipping"
                )
            else:
                # Everything is derived from ``logits`` alone — the stored ``scores`` field
                # is being retired, so masking must not depend on it. Recompute the model's
                # full softmax (over every class) from the logits, then multiply each class
                # by its prior weight. That equals a softmax of ``logits + log(prior)``
                # without evaluating log(0), so a hard mask needs no special case: a class
                # with prior 0 is exactly zero and can never win argmax or carry probability.
                shifted = np.asarray(logits, dtype=float)
                shifted -= shifted.max()  # stabilises exp without changing the softmax
                full_softmax = np.exp(shifted)
                full_softmax /= full_softmax.sum()  # p over all classes; matches the retired ``scores``

                weighted = full_softmax * prior
                weighted_sum = weighted.sum()
                if not weighted_sum > 0:
                    # Every class with a non-zero prior underflowed to zero, so there is
                    # nothing to renormalise or to pick. The comparison is also false for NaN.
                    task_logger.warning(
                        f"Classification {classification.pk}: no class with a non-zero weight "
                        "has any probability; skipping"
                    )
                    continue
                top_index = int(np.argmax(weighted))  # a class with prior 0 is 0 and cannot win

                if reweight:
                    # Renormalise: the weighted scores sum to 1.
                    new_scores_np = weighted / weighted_sum
                else:
                    # No renormalisation (hard mask only): classes in the list keep their
                    # original absolute probability; the rest are zero. Winner is unchanged.
                    new_scores_np = weighted
                new_scores = new_scores_np.tolist()
                score = float(new_scores_np[top_index])

                # No-change short-circuit: if the weights shifted no probability (the classes
                # this taxa list down-weights carried ~zero probability here), leave the row
                # untouched. Compared against the unmasked softmax, not the stored scores.
                if np.allclose(full_softmax, new_scores_np, atol=1e-9):
                    task_logger.debug(f"Classification {classification.pk} unchanged by masking; skipping")
                else:
                    # Never None: a class without a taxon has prior 0. The taxon is outside
                    # the taxa list when a down-weighted class still wins.
                    top_taxon = index_to_taxon.get(top_index)

                    classification.terminal = False
                    classification.updated_at = timestamp

                    new_classification = Classification(
                        detection=classification.detection,
                        taxon=top_taxon,
                        algorithm=new_algorithm,
                        category_map=new_algorithm.category_map,
                        score=score,
                        scores=new_scores,
                        # Not copied: the source row keeps the logits, reachable through
                        # ``applied_to``, and a copy per masked row filled a production disk.
                        # ``scores`` holds the masked result. See #1404.
                        logits=None,
                        terminal=True,
                        timestamp=classification.timestamp,
                        applied_to=classification,
                        job=job,
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                    classifications_to_demote.append(classification)
                    classifications_to_add.append(new_classification)
                    masked_count += 1

                    detection = classification.detection
                    if detection is not None and detection.occurrence is not None:
                        occurrences_to_update.add(detection.occurrence)
                        # The occurrence's result carries the figures of its winning detection:
                        # the one whose masked classification scores highest (see AlgorithmResultWriter).
                        results.note(
                            detection.occurrence,
                            {
                                # The classifier's own figure: taken from the unweighted
                                # softmax, so it is the same at every weight.
                                "excluded_probability": float(1.0 - (full_softmax * in_list).sum()),
                                "excluded_probability_after": float(new_scores_np[not_in_list].sum()),
                                "new_winner_original_rank": int((full_softmax > full_softmax[top_index]).sum()) + 1,
                                "winner_in_list": bool(in_list[top_index]),
                            },
                            rank=score,
                        )

        # Flush after every batch, even when nothing was accumulated, so the job
        # health-check sees a heartbeat during stretches where masking is a no-op.
        with transaction.atomic():
            if classifications_to_demote:
                Classification.objects.bulk_update(classifications_to_demote, ["terminal", "updated_at"])
            results.start_batch(occurrences_to_update, classifications_to_add)
            if classifications_to_add:
                Classification.objects.bulk_create(classifications_to_add)
            # Count an occurrence only when saving its new terminal classification
            # actually changes the determination. Re-saving recomputes it in place,
            # so an occurrence pinned to a human identification keeps its taxon
            # and must not inflate the metric.
            for occurrence in occurrences_to_update:
                prev = occurrence.determination_id
                occurrence.save(update_determination=True)
                if occurrence.pk is not None and occurrence.determination_id != prev:
                    changed_occurrence_ids.add(occurrence.pk)
            results.finish_batch(occurrences_to_update)

        classifications_to_demote.clear()
        classifications_to_add.clear()
        occurrences_to_update.clear()

        if on_batch is not None:
            on_batch(
                {
                    "classifications_checked": i,
                    "classifications_total": total,
                    "classifications_masked": masked_count,
                    "occurrences_updated": len(changed_occurrence_ids),
                }
            )

    task_logger.info(
        f"Re-scored {masked_count} of {total} classifications; updated {len(changed_occurrence_ids)} occurrences."
    )
    return {
        "classifications_checked": total,
        "classifications_masked": masked_count,
        "occurrences_updated": len(changed_occurrence_ids),
    }


def _weight_token(weight: float) -> str:
    """The weight as written in a masking Algorithm key: 0.01 gives ``0p01``.

    The key is a slug, which allows no dot, so ``p`` stands for the decimal point.
    """
    return f"{weight:.{WEIGHT_DECIMALS}f}".rstrip("0").rstrip(".").replace(".", "p")


class ClassMaskingTask(BasePostProcessingTask):
    key = "class_masking"
    name = "Class masking"
    config_schema = ClassMaskingConfig
    result_models = (ClassMaskingResultData,)

    def _get_or_create_masking_algorithm(
        self, source_algorithm: Algorithm, taxa_list: TaxaList, *, reweight: bool, out_of_list_weight: float
    ) -> Algorithm:
        """Get or create the output algorithm for this source algorithm, taxa list and weight.

        One masking algorithm per (source algorithm, taxa list, out-of-list weight)
        keeps provenance reproducible: re-running the same mask reuses the same
        Algorithm row. The weight is part of the identity because it changes which
        species can be named. A hard mask (weight 0) also has one algorithm per
        reweight mode, because its two modes persist different score semantics
        (renormalised vs original absolute); a soft mask only has renormalised
        scores. The hard-mask key carries the mode and no weight, so it stays equal
        to the keys of hard-mask algorithms already stored. The category map is the
        source map (indices still align with the masked score vector) and is
        persisted — earlier code set it in memory only, so masked classifications
        referenced a null map.
        """
        base_key = f"{source_algorithm.key}_filtered_by_taxa_list_{taxa_list.pk}"
        if out_of_list_weight > 0:
            key = f"{base_key}_weight_{_weight_token(out_of_list_weight)}"
            summary = f"out-of-list weight {out_of_list_weight:g}"
            name = f"{source_algorithm.name} (weighted by taxa list {taxa_list.name}, {summary})"
        else:
            mode = "reweighted" if reweight else "absolute"
            key = f"{base_key}_{mode}"
            summary = f"{mode} scores"
            name = f"{source_algorithm.name} (filtered by taxa list {taxa_list.name}, {summary})"
        algorithm, created = Algorithm.objects.get_or_create(
            key=key,
            defaults={
                "name": name,
                "description": (
                    f"Classifications from {source_algorithm.name} re-scored against taxa list "
                    f"{taxa_list.name} ({summary})"
                ),
                "task_type": AlgorithmTaskType.CLASSIFICATION.value,
                "category_map": source_algorithm.category_map,
            },
        )
        if not created and algorithm.category_map_id != source_algorithm.category_map_id:
            algorithm.category_map = source_algorithm.category_map
            algorithm.save(update_fields=["category_map"])
        return algorithm

    def _scoped_classifications(
        self, config: ClassMaskingConfig, source_algorithm: Algorithm, masking_algorithm: Algorithm
    ) -> tuple[QuerySet[Classification], str]:
        """Resolve the terminal classifications to re-score from the config's scope.

        ``config_schema`` guarantees exactly one scope id is set, so the single
        ``else`` branch is sound.

        Do not add ``.distinct()`` while both scopes filter a to-one path: neither
        can duplicate a row, and de-duplicating sorts the ``logits`` and ``scores``
        arrays, which measured 208s versus 0.5s on a 55,530-row scope. Broadening
        either scope to match several collections or a whole project would fan out
        and need de-duplication again — restrict the columns first. See #1376.

        Sources already re-scored by ``masking_algorithm`` are excluded via the
        ``applied_to`` lineage, so a source is masked at most once per masking
        algorithm even if it becomes terminal again later. A taxa list is identified
        by primary key, not contents — re-masking against an edited list needs a new
        list. See #1368.
        """
        base = (
            Classification.objects.filter(
                terminal=True,
                algorithm=source_algorithm,
                scores__isnull=False,
                logits__isnull=False,
            )
            # If another task needs this replay guard, hoist it to a
            # ClassificationQuerySet method (e.g. not_derived_by(algorithm))
            # rather than copying the exclude.
            .exclude(derived_classifications__algorithm=masking_algorithm).select_related(
                "detection", "detection__occurrence"
            )
        )

        if config.occurrence_id is not None:
            if not Occurrence.objects.filter(pk=config.occurrence_id).exists():
                raise ValueError(f"Occurrence {config.occurrence_id} not found")
            return (
                base.filter(detection__occurrence_id=config.occurrence_id),
                f"occurrence {config.occurrence_id}",
            )

        try:
            collection = SourceImageCollection.objects.get(pk=config.source_image_collection_id)
        except SourceImageCollection.DoesNotExist:
            raise ValueError(f"SourceImageCollection {config.source_image_collection_id} not found")
        return (
            base.filter(detection__source_image__collections=collection),
            f"collection {collection.pk}",
        )

    def run(self) -> None:
        config: ClassMaskingConfig = self.config  # type: ignore[assignment]
        self.logger.info(f"=== Starting {self.name} ===")

        try:
            source_algorithm = Algorithm.objects.get(pk=config.algorithm_id)
        except Algorithm.DoesNotExist:
            raise ValueError(f"Algorithm {config.algorithm_id} not found")
        try:
            taxa_list = TaxaList.objects.get(pk=config.taxa_list_id)
        except TaxaList.DoesNotExist:
            raise ValueError(f"TaxaList {config.taxa_list_id} not found")
        if not source_algorithm.category_map:
            raise ValueError(f"Algorithm '{source_algorithm.name}' has no category map; cannot mask classes.")

        masking_algorithm = self._get_or_create_masking_algorithm(
            source_algorithm, taxa_list, reweight=config.reweight, out_of_list_weight=config.out_of_list_weight
        )
        classifications, scope_desc = self._scoped_classifications(config, source_algorithm, masking_algorithm)
        self.logger.info(
            f"Applying class masking on {scope_desc} using taxa list {taxa_list.pk} "
            f"with out-of-list weight {config.out_of_list_weight:g}"
        )

        def _on_setup(total: int) -> None:
            self.update_progress(0.0)
            self.report_stage_metrics({"classifications_total": total})

        def _on_batch(m: dict) -> None:
            total = m["classifications_total"]
            self.update_progress(m["classifications_checked"] / total if total else 1.0)
            self.report_stage_metrics(
                {
                    "classifications_checked": m["classifications_checked"],
                    "classifications_masked": m["classifications_masked"],
                    "occurrences_updated": m["occurrences_updated"],
                }
            )

        metrics = make_classifications_filtered_by_taxa_list(
            classifications=classifications,
            taxa_list=taxa_list,
            algorithm=source_algorithm,
            new_algorithm=masking_algorithm,
            reweight=config.reweight,
            out_of_list_weight=config.out_of_list_weight,
            task_logger=self.logger,
            on_setup=_on_setup,
            on_batch=_on_batch,
            job=self.job,
        )
        self.report_stage_metrics(metrics)
        self.logger.info(f"=== Completed {self.name} ===")
