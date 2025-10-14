import logging
from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from ami.main.models import Classification, Identification, Taxon
from ami.ml.post_processing.base import BasePostProcessingTask, register_postprocessing_task

logger = logging.getLogger(__name__)


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


@register_postprocessing_task
class RankRollupTask(BasePostProcessingTask):
    """Post-processing task that rolls up low-confidence classifications
    to higher ranks using aggregated scores.
    """

    key = "rank_rollup"
    name = "Rank rollup"

    DEFAULT_THRESHOLDS = {"species": 0.8, "genus": 0.6, "family": 0.4}
    ROLLUP_ORDER = ["species", "genus", "family"]

    def run(self) -> None:
        job = self.job
        self.logger.info(f"Starting {self.name} task for job {job.pk if job else 'N/A'}")

        # ---- Read config parameters ----
        config = self.config or {}
        collection_id = config.get("source_image_collection_id")
        thresholds = config.get("thresholds", self.DEFAULT_THRESHOLDS)
        rollup_order = config.get("rollup_order", self.ROLLUP_ORDER)

        if not collection_id:
            self.logger.warning("No 'source_image_collection_id' provided in config. Aborting task.")
            return

        self.logger.info(
            f"Config loaded: collection_id={collection_id}, thresholds={thresholds}, rollup_order={rollup_order}"
        )

        qs = Classification.objects.filter(
            terminal=True,
            taxon__isnull=False,
            detection__source_image__collections__id=collection_id,
        )

        total = qs.count()
        self.logger.info(f"Found {total} terminal classifications to process for collection {collection_id}")

        updated_occurrences = []

        with transaction.atomic():
            for i, clf in enumerate(qs.iterator(), start=1):
                self.logger.info(f"Processing classification #{clf.pk} (taxon={clf.taxon}, score={clf.score:.3f})")

                if not clf.scores:
                    self.logger.warning(f"Skipping classification #{clf.pk}: no scores available")
                    continue
                if not clf.category_map:
                    self.logger.warning(f"Skipping classification #{clf.pk}: no category_map assigned")
                    continue

                taxon_scores = defaultdict(float)

                for idx, score in enumerate(clf.scores):
                    label = clf.category_map.labels[idx]
                    if not label:
                        continue

                    taxon = Taxon.objects.filter(name=label).first()
                    if not taxon:
                        self.logger.debug(f"Skipping label '{label}' (no matching Taxon in DB)")
                        continue

                    for rank in rollup_order:
                        ancestor = find_ancestor_by_parent_chain(taxon, rank)
                        if ancestor:
                            taxon_scores[ancestor] += score
                            self.logger.debug(f"    + Added {score:.3f} to ancestor {ancestor.name} ({rank})")

                new_taxon = None
                new_score = None
                for rank in rollup_order:
                    threshold = thresholds.get(rank, 1.0)
                    candidates = {t: s for t, s in taxon_scores.items() if t.rank == rank}

                    if not candidates:
                        self.logger.debug(f"No candidates found at rank {rank}")
                        continue

                    best_taxon, best_score = max(candidates.items(), key=lambda kv: kv[1])
                    self.logger.debug(
                        f"Best at rank {rank}: {best_taxon.name} ({best_score:.3f}) [threshold={threshold}]"
                    )

                    if best_score >= threshold:
                        new_taxon, new_score = best_taxon, best_score
                        self.logger.info(f"Rollup decision: {new_taxon.name} ({rank}) with score {new_score:.3f}")
                        break

                if new_taxon and new_taxon != clf.taxon:
                    self.logger.info(f"Rolling up {clf.taxon} → {new_taxon} ({new_taxon.rank})")

                    with transaction.atomic():
                        Classification.objects.filter(detection=clf.detection, terminal=True).update(terminal=False)
                        Classification.objects.create(
                            detection=clf.detection,
                            taxon=new_taxon,
                            score=new_score,
                            terminal=True,
                            algorithm=self.algorithm,
                            timestamp=timezone.now(),
                        )

                    occurrence = clf.detection.occurrence
                    if occurrence:
                        Identification.objects.create(
                            occurrence=occurrence,
                            taxon=new_taxon,
                            user=None,
                            comment=f"Auto-set by {self.name} post-processing task",
                        )
                        updated_occurrences.append(occurrence.pk)

                    self.logger.info(
                        f"Rolled up occurrence {occurrence.pk}: {clf.taxon} → {new_taxon} "
                        f"({new_taxon.rank}) with rolled-up score={new_score:.3f}"
                    )
                else:
                    self.logger.info(f"No rollup applied for classification #{clf.pk} (taxon={clf.taxon})")

                # 🔹 Periodic progress updates
                if i % 50 == 0 or i == total:
                    progress = i / total if total > 0 else 1.0
                    self.update_progress(progress)

        self.logger.info(f"Rank rollup completed. Updated {len(updated_occurrences)} occurrences.")
        self.logger.info(f"{self.name} task finished for collection {collection_id}.")
