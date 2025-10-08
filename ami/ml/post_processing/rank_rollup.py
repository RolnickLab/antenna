import logging
from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from ami.jobs.models import Job
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
    name = "Rank Rollup"

    DEFAULT_THRESHOLDS = {"species": 0.8, "genus": 0.6, "family": 0.4}
    ROLLUP_ORDER = ["species", "genus", "family"]

    def run(self, job: "Job") -> None:
        job.logger.info(f"Running Rank Rollup task for job {job.pk}")

        # ---- Read config parameters ----
        config = self.config or {}
        collection_id = config.get("source_image_collection_id")
        thresholds = config.get("thresholds", self.DEFAULT_THRESHOLDS)
        rollup_order = config.get("rollup_order", self.ROLLUP_ORDER)

        if not collection_id:
            job.logger.warning("No 'source_image_collection_id' provided in job config. Aborting task.")
            return

        job.logger.info(f"Config: collection_id={collection_id}, thresholds={thresholds}, rollup_order={rollup_order}")

        qs = Classification.objects.filter(
            terminal=True,
            taxon__isnull=False,
            detection__source_image__collections__id=collection_id,
        )

        updated_occurrences = []

        with transaction.atomic():
            for clf in qs:
                if not clf.scores or not clf.category_map:
                    continue

                taxon_scores = defaultdict(float)

                for idx, score in enumerate(clf.scores):
                    label = clf.category_map.labels[idx]
                    if not label:
                        continue

                    taxon = Taxon.objects.filter(name=label).first()
                    if not taxon:
                        continue

                    for rank in rollup_order:
                        ancestor = find_ancestor_by_parent_chain(taxon, rank)
                        if ancestor:
                            taxon_scores[ancestor] += score

                new_taxon = None
                new_score = None
                for rank in rollup_order:
                    threshold = thresholds.get(rank, 1.0)
                    candidates = {t: s for t, s in taxon_scores.items() if t.rank == rank}
                    if not candidates:
                        continue
                    best_taxon, best_score = max(candidates.items(), key=lambda kv: kv[1])
                    if best_score >= threshold:
                        new_taxon, new_score = best_taxon, best_score
                        break

                if new_taxon and new_taxon != clf.taxon:
                    with transaction.atomic():
                        Classification.objects.filter(detection=clf.detection, terminal=True).update(terminal=False)

                        Classification.objects.create(
                            detection=clf.detection,
                            taxon=new_taxon,
                            score=new_score,
                            terminal=True,
                            algorithm=clf.algorithm,
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

                    job.logger.info(
                        f"Rolled up occurrence {occurrence.pk}: {clf.taxon} to{new_taxon} "
                        f"({new_taxon.rank}) with rolled-up score={new_score:.3f}"
                    )

        job.logger.info(f"Rank rollup completed. Updated {len(updated_occurrences)} occurrences.")
        job.logger.info(f"Rank rollup completed for collection {collection_id}.")
