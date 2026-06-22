import logging
from collections import defaultdict

import pydantic
from django.db import transaction
from django.utils import timezone

from ami.main.models import Classification, Taxon
from ami.ml.models.algorithm import AlgorithmCategoryMap
from ami.ml.post_processing.base import BasePostProcessingTask

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS = {"SPECIES": 0.8, "GENUS": 0.6, "FAMILY": 0.4}
DEFAULT_ROLLUP_ORDER = ["SPECIES", "GENUS", "FAMILY"]


class RankRollupConfig(pydantic.BaseModel):
    source_image_collection_id: int
    # Minimum aggregated score required to roll a classification up to each rank.
    thresholds: dict[str, float] = DEFAULT_THRESHOLDS
    # Ranks to try, finest first; the first whose aggregated score clears its
    # threshold wins.
    rollup_order: list[str] = DEFAULT_ROLLUP_ORDER

    @pydantic.validator("thresholds")
    def _validate_thresholds(cls, value: dict[str, float]) -> dict[str, float]:
        normalised: dict[str, float] = {}
        for rank, threshold in value.items():
            if not (0.0 < threshold <= 1.0):
                raise ValueError(f"Threshold for {rank} must be in (0, 1]")
            normalised[rank.upper()] = threshold
        return normalised

    @pydantic.validator("rollup_order")
    def _uppercase_order(cls, value: list[str]) -> list[str]:
        return [rank.upper() for rank in value]

    class Config:
        extra = "forbid"


def find_ancestor_by_parent_chain(taxon, target_rank: str):
    """Climb up parent relationships until a taxon with the target rank is found."""
    if not taxon:
        return None

    target_rank = target_rank.upper()

    current = taxon
    while current:
        if current.rank.upper() == target_rank:
            return current
        current = current.parent

    return None


class RankRollupTask(BasePostProcessingTask):
    """Post-processing task that rolls up low-confidence classifications
    to higher ranks using aggregated scores.
    """

    key = "rank_rollup"
    name = "Rank rollup"
    config_schema = RankRollupConfig

    def run(self) -> None:
        config: RankRollupConfig = self.config  # type: ignore[assignment]
        job = self.job
        self.logger.info(f"Starting {self.name} task for job {job.pk if job else 'N/A'}")

        collection_id = config.source_image_collection_id
        thresholds = config.thresholds
        rollup_order = config.rollup_order

        self.logger.info(
            f"Config loaded: collection_id={collection_id}, thresholds={thresholds}, rollup_order={rollup_order}"
        )

        # select_related the per-row relations the loop touches (category_map for
        # labels, detection/occurrence for the rollup write) so the body issues no
        # per-classification queries.
        qs = (
            Classification.objects.filter(
                terminal=True,
                taxon__isnull=False,
                detection__source_image__collections__id=collection_id,
            )
            .select_related("category_map", "taxon", "detection", "detection__occurrence")
            .distinct()
        )

        total = qs.count()
        self.logger.info(f"Found {total} terminal classifications to process for collection {collection_id}")

        # Pre-load every label across the distinct category maps in one pass (two
        # queries total), instead of dereferencing clf.category_map per row.
        category_map_ids = list(qs.values_list("category_map_id", flat=True).distinct())
        all_labels: set[str] = set()
        for category_map in AlgorithmCategoryMap.objects.filter(pk__in=category_map_ids):
            if category_map.labels:
                all_labels.update(label for label in category_map.labels if label)

        label_to_taxon = {}
        if all_labels:
            for taxon in Taxon.objects.filter(name__in=all_labels).select_related("parent"):
                label_to_taxon[taxon.name] = taxon
        self.logger.info(f"Pre-loaded {len(label_to_taxon)} taxa from {len(all_labels)} unique labels")

        updated_occurrences = []

        with transaction.atomic():
            for i, clf in enumerate(qs.iterator(), start=1):
                score_str = f"{clf.score:.3f}" if clf.score is not None else "N/A"
                self.logger.info(f"Processing classification #{clf.pk} (taxon={clf.taxon}, score={score_str})")

                if not clf.scores:
                    self.logger.info(f"Skipping classification #{clf.pk}: no scores available")
                    continue
                if not clf.category_map:
                    self.logger.info(f"Skipping classification #{clf.pk}: no category_map assigned")
                    continue

                taxon_scores = defaultdict(float)

                for idx, score in enumerate(clf.scores):
                    label = clf.category_map.labels[idx]
                    if not label:
                        continue

                    taxon = label_to_taxon.get(label)
                    if not taxon:
                        self.logger.debug(f"Skipping label '{label}' (no matching Taxon found)")
                        continue

                    for rank in rollup_order:
                        ancestor = find_ancestor_by_parent_chain(taxon, rank)
                        if ancestor:
                            taxon_scores[ancestor] += score
                            self.logger.debug(f"    + Added {score:.3f} to ancestor {ancestor.name} ({rank})")

                new_taxon = None
                new_score = None
                scores_str = {t.name: s for t, s in taxon_scores.items()}
                self.logger.info(f"Aggregated taxon scores: {scores_str}")
                for rank in rollup_order:
                    threshold = thresholds.get(rank, 1.0)
                    candidates = {t: s for t, s in taxon_scores.items() if t.rank == rank}

                    if not candidates:
                        self.logger.info(f"No candidates found at rank {rank}")
                        continue

                    best_taxon, best_score = max(candidates.items(), key=lambda kv: kv[1])
                    self.logger.info(
                        f"Best at rank {rank}: {best_taxon.name} ({best_score:.3f}) [threshold={threshold}]"
                    )

                    if best_score >= threshold:
                        new_taxon, new_score = best_taxon, best_score
                        self.logger.info(f"Rollup decision: {new_taxon.name} ({rank}) with score {new_score:.3f}")
                        break

                if new_taxon and new_taxon != clf.taxon:
                    self.logger.info(f"Rolling up {clf.taxon} => {new_taxon} ({new_taxon.rank})")

                    # Mark all classifications for this detection as non-terminal
                    Classification.objects.filter(detection=clf.detection).update(terminal=False)
                    Classification.objects.create(
                        detection=clf.detection,
                        taxon=new_taxon,
                        score=new_score,
                        terminal=True,
                        algorithm=self.algorithm,
                        timestamp=timezone.now(),
                        applied_to=clf,
                    )

                    occurrence = clf.detection.occurrence
                    if occurrence:
                        occurrence.save(update_determination=True)
                        updated_occurrences.append(occurrence)
                        self.logger.info(
                            f"Rolled up occurrence {occurrence.pk}: {clf.taxon} => {new_taxon} "
                            f"({new_taxon.rank}) with rolled-up score={new_score:.3f}"
                        )
                    else:
                        self.logger.warning(f"Detection #{clf.detection.pk} has no occurrence; skipping.")
                else:
                    self.logger.info(f"No rollup applied for classification #{clf.pk} (taxon={clf.taxon})")

                # Update progress every 10 iterations
                if i % 10 == 0 or i == total:
                    progress = i / total if total > 0 else 1.0
                    self.update_progress(progress)

        self.report_stage_metrics(
            {
                "classifications_checked": total,
                "occurrences_rolled_up": len(updated_occurrences),
            }
        )
        self.logger.info(f"Rank rollup completed. Updated {len(updated_occurrences)} occurrences.")
        self.logger.info(f"{self.name} task finished for collection {collection_id}.")
