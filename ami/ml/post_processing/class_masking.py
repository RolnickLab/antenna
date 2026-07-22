import logging
from collections.abc import Callable

import numpy as np
import pydantic
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from ami.main.models import Classification, Occurrence, SourceImageCollection, TaxaList
from ami.ml.models.algorithm import Algorithm, AlgorithmTaskType
from ami.ml.post_processing.base import BasePostProcessingTask

logger = logging.getLogger(__name__)


class ClassMaskingConfig(pydantic.BaseModel):
    # Scope: exactly one of these identifies which classifications to re-score. A
    # capture set is the bulk path; a single occurrence is the spot/dev path (fast
    # feedback while tuning a taxa list). This mirrors SmallSizeFilterConfig's
    # discriminated-scope shape — the shared pattern for per-occurrence triggers.
    source_image_collection_id: int | None = None
    occurrence_id: int | None = None
    # The taxa list to keep: classes whose taxon is not in this list are masked out.
    taxa_list_id: int
    # The source classifier whose terminal classifications are re-scored.
    algorithm_id: int
    # When True (default), renormalise the kept classes' scores to sum to 1 after
    # masking. When False, the kept classes retain their original absolute scores and
    # the excluded classes are zeroed; the chosen species is identical either way.
    reweight: bool = True

    @pydantic.root_validator(skip_on_failure=True)
    def _exactly_one_scope(cls, values: dict) -> dict:
        scopes = [values.get("source_image_collection_id"), values.get("occurrence_id")]
        if sum(s is not None for s in scopes) != 1:
            raise ValueError("Provide exactly one of source_image_collection_id or occurrence_id")
        return values

    class Config:
        extra = "forbid"


def make_classifications_filtered_by_taxa_list(
    classifications: QuerySet[Classification],
    taxa_list: TaxaList,
    algorithm: Algorithm,
    new_algorithm: Algorithm,
    *,
    batch_size: int = 200,
    reweight: bool = True,
    task_logger: logging.Logger = logger,
    on_setup: Callable[[int], None] | None = None,
    on_batch: Callable[[dict], None] | None = None,
) -> dict[str, int]:
    """Re-score ``classifications`` by masking out classes absent from ``taxa_list``.

    For each terminal classification produced by ``algorithm``, the logits of
    classes whose taxon is not in ``taxa_list`` are masked, the softmax is
    renormalised over the remaining classes (or, when ``reweight=False``, the kept
    classes retain their original absolute scores), and a new terminal classification
    (attributed to ``new_algorithm``, linked back via ``applied_to``) records the
    masked prediction. The original classification is demoted to non-terminal.

    Commits in batches of ``batch_size`` so memory stays bounded and the job
    health-check reaper sees regular heartbeats. ``on_batch`` is called after every
    flush with running counters:
    ``{"classifications_checked": i, "classifications_total": total,
       "classifications_masked": masked_count, "occurrences_updated": n_changed}``.

    ``on_setup`` is called once with the number of classifications in scope, before
    the first row is processed, so a long run reports what it found up front.

    ``occurrences_updated`` counts only occurrences whose determination actually
    changed (not just any occurrence touched), matching the size-filter convention.

    Returns final counters (checked / masked / occurrences updated) for stage metrics.
    """
    taxa_in_list = set(taxa_list.taxa.all())

    total = classifications.count()
    task_logger.info(f"Found {total} terminal classifications with scores to re-score.")

    if not algorithm.category_map:
        raise ValueError(f"Algorithm {algorithm} does not have a category map.")
    category_map = algorithm.category_map

    # Resolve each category's taxon once. Indices absent from this map, or whose
    # taxon is not in the taxa list, are masked. Building included from the taxa
    # list (rather than excluded from the map) means a class with no resolvable
    # taxon is masked too, never silently kept.
    task_logger.info(f"Retrieving category map with Taxa instances for algorithm {algorithm}")
    category_map_with_taxa = category_map.with_taxa()
    index_to_taxon = {int(category["index"]): category["taxon"] for category in category_map_with_taxa}
    num_categories = len(category_map.labels)
    included_indices = [i for i in range(num_categories) if index_to_taxon.get(i) in taxa_in_list]
    excluded_indices = [i for i in range(num_categories) if i not in set(included_indices)]

    if not included_indices:
        raise ValueError(
            f"Taxa list '{taxa_list.name}' excludes every class in algorithm '{algorithm.name}'s "
            "category map; there is nothing to keep."
        )

    task_logger.info(
        f"Category map has {num_categories} classes, "
        f"{len(excluded_indices)} masked, {len(included_indices)} kept, "
        f"{total} classifications to check"
    )

    classifications_to_demote: list[Classification] = []
    classifications_to_add: list[Classification] = []
    occurrences_to_update: set[Occurrence] = set()
    # Tracks occurrences whose determination actually changed across all batches.
    changed_occurrence_ids: set[int] = set()

    timestamp = timezone.now()
    masked_count = 0

    # Sizing the scope and expanding the category map both take time on a large
    # classifier, so report before touching a row.
    if on_setup is not None:
        on_setup(total)

    for i, classification in enumerate(classifications.iterator(chunk_size=batch_size), start=1):
        logits = classification.logits
        if not isinstance(logits, list) or not all(isinstance(x, (int, float)) for x in logits):
            raise ValueError(f"Logits for classification {classification.pk} are not a list of numbers: {logits}")
        elif len(logits) != num_categories:
            task_logger.warning(
                f"Classification {classification.pk}: {len(logits)} logits != {num_categories} categories; skipping"
            )
        else:
            # Everything is derived from ``logits`` alone — the stored ``scores`` field
            # is being retired, so masking must not depend on it. Recompute the model's
            # full softmax (over every class) from the logits, then drop the excluded
            # classes to exactly zero. An excluded class can never win argmax or carry
            # probability.
            shifted = np.asarray(logits, dtype=float)
            shifted -= shifted.max()  # stabilises exp without changing the softmax
            full_softmax = np.exp(shifted)
            full_softmax /= full_softmax.sum()  # p over all classes; matches the retired ``scores``

            kept = full_softmax.copy()
            kept[excluded_indices] = 0.0
            kept_sum = kept.sum()  # > 0: at least one class is kept (guaranteed upstream)
            top_index = int(np.argmax(kept))  # over kept classes only (excluded are 0)

            if reweight:
                # Renormalise: excluded classes stay 0; kept classes sum to 1.
                new_scores_np = kept / kept_sum
            else:
                # No renormalisation: kept classes keep their original absolute
                # probability; excluded classes are zeroed. Winner is unchanged.
                new_scores_np = kept
            new_scores = new_scores_np.tolist()
            score = float(new_scores_np[top_index])

            # No-change short-circuit: if masking shifted no probability (the classes
            # this taxa list drops carried ~zero probability here), leave the row
            # untouched. Compared against the unmasked softmax, not the stored scores.
            if np.allclose(full_softmax, new_scores_np, atol=1e-9):
                task_logger.debug(f"Classification {classification.pk} unchanged by masking; skipping")
            else:
                top_taxon = index_to_taxon.get(top_index)  # guaranteed in taxa_in_list (top_index is kept)

                classification.terminal = False
                classification.updated_at = timestamp

                new_classification = Classification(
                    detection=classification.detection,
                    taxon=top_taxon,
                    algorithm=new_algorithm,
                    category_map=new_algorithm.category_map,
                    score=score,
                    scores=new_scores,
                    # Store the raw logits unchanged (JSON-safe): the mask is fully captured
                    # by ``scores`` (dropped classes -> 0) and the ``applied_to`` lineage.
                    logits=logits,
                    terminal=True,
                    timestamp=classification.timestamp,
                    applied_to=classification,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
                classifications_to_demote.append(classification)
                classifications_to_add.append(new_classification)
                masked_count += 1

                detection = classification.detection
                if detection is not None and detection.occurrence is not None:
                    occurrences_to_update.add(detection.occurrence)

        # Flush every batch_size items and at the final item. The flush fires even
        # when nothing was accumulated so the job health-check sees a heartbeat during
        # stretches where masking is a no-op (all short-circuited).
        if i % batch_size == 0 or i == total:
            with transaction.atomic():
                if classifications_to_demote:
                    Classification.objects.bulk_update(classifications_to_demote, ["terminal", "updated_at"])
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


class ClassMaskingTask(BasePostProcessingTask):
    key = "class_masking"
    name = "Class masking"
    config_schema = ClassMaskingConfig

    def _get_or_create_masking_algorithm(
        self, source_algorithm: Algorithm, taxa_list: TaxaList, *, reweight: bool
    ) -> Algorithm:
        """Get or create the output algorithm for this (source algorithm, taxa list, reweight mode).

        One masking algorithm per (source algorithm, taxa list, reweight mode)
        keeps provenance reproducible: re-running the same mask reuses the same
        Algorithm row. The reweight mode is part of the identity because the two
        modes persist different score semantics (renormalised vs original
        absolute), so a masked classification's ``applied_to.algorithm`` can tell
        them apart. Its category map is the source map (indices still align with
        the masked score vector) and is persisted — earlier code set it in memory
        only, so masked classifications referenced a null map.
        """
        mode = "reweighted" if reweight else "absolute"
        algorithm, created = Algorithm.objects.get_or_create(
            key=f"{source_algorithm.key}_filtered_by_taxa_list_{taxa_list.pk}_{mode}",
            defaults={
                "name": f"{source_algorithm.name} (filtered by taxa list {taxa_list.name}, {mode} scores)",
                "description": (
                    f"Classifications from {source_algorithm.name} re-scored against taxa list "
                    f"{taxa_list.name} ({mode} scores)"
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
        self, config: ClassMaskingConfig, source_algorithm: Algorithm
    ) -> tuple[QuerySet[Classification], str]:
        """Resolve the terminal classifications to re-score from the config's scope.

        ``config_schema`` guarantees exactly one scope id is set, so the single
        ``else`` branch is sound.

        Do not add ``.distinct()`` while both scopes filter a to-one path: neither
        can duplicate a row, and de-duplicating sorts the ``logits`` and ``scores``
        arrays, which measured 208s versus 0.5s on a 55,530-row scope. Broadening
        either scope to match several collections or a whole project would fan out
        and need de-duplication again — restrict the columns first. See #1376.
        """
        base = Classification.objects.filter(
            terminal=True,
            algorithm=source_algorithm,
            scores__isnull=False,
            logits__isnull=False,
        ).select_related("detection", "detection__occurrence")

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
            source_algorithm, taxa_list, reweight=config.reweight
        )
        classifications, scope_desc = self._scoped_classifications(config, source_algorithm)
        self.logger.info(f"Applying class masking on {scope_desc} using taxa list {taxa_list.pk}")

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
            task_logger=self.logger,
            on_setup=_on_setup,
            on_batch=_on_batch,
        )
        self.report_stage_metrics(metrics)
        self.logger.info(f"=== Completed {self.name} ===")
