from django.db import transaction
from django.utils import timezone

from ami.jobs.models import Job
from ami.main.models import Detection, Identification, SourceImageCollection, Taxon, TaxonRank
from ami.ml.post_processing.base import BasePostProcessingTask, register_postprocessing_task


@register_postprocessing_task
class SmallSizeFilter(BasePostProcessingTask):
    key = "small_size_filter"
    name = "Small Size Filter"

    def run(self, job: "Job") -> None:
        threshold = self.config.get("size_threshold", 0.01)
        collection_id = self.config.get("source_image_collection_id")
        # Get or create the "Not identifiable" taxon

        not_identifiable_taxon, _ = Taxon.objects.get_or_create(
            name="Not identifiable",
            defaults={
                "rank": TaxonRank.UNKNOWN,
                "notes": "Auto-generated taxon for small size filter",
            },
        )
        job.logger.info(f"=== Starting {self.name} ===")

        if not collection_id:
            msg = "Missing required config param: source_image_collection_id"
            job.logger.error(msg)
            raise ValueError(msg)

        try:
            collection = SourceImageCollection.objects.get(pk=collection_id)
            job.logger.info(f"Loaded SourceImageCollection {collection_id} " f"(Project={collection.project})")
        except SourceImageCollection.DoesNotExist:
            msg = f"SourceImageCollection {collection_id} not found"
            job.logger.error(msg)
            raise ValueError(msg)

        detections = Detection.objects.filter(source_image__collections=collection)
        total = detections.count()
        job.logger.info(f"Found {total} detections in collection {collection_id}")

        modified = 0

        for det in detections.iterator():
            bbox = det.get_bbox()
            if not bbox:
                job.logger.debug(f"Detection {det.pk}: no bbox, skipping")
                continue

            img_w, img_h = det.source_image.width, det.source_image.height
            if not img_w or not img_h:
                job.logger.debug(f"Detection {det.pk}: missing source image dims, skipping")
                continue

            det_area = det.width() * det.height()
            img_area = img_w * img_h
            rel_area = det_area / img_area if img_area else 0

            job.logger.debug(
                f"Detection {det.pk}: area={det_area}, rel_area={rel_area:.4f}, " f"threshold={threshold:.4f}"
            )

            if rel_area < threshold:
                with transaction.atomic():
                    # Mark existing classifications as non-terminal
                    det.classifications.update(terminal=False)

                    # Create the new "Not identifiable" classification
                    det.classifications.create(
                        detection=det,
                        taxon=not_identifiable_taxon,
                        score=1.0,
                        terminal=True,
                        timestamp=timezone.now(),
                        algorithm=self.algorithm,
                    )
                    # Also create/update Identification for the linked occurrence
                    if det.occurrence:
                        Identification.objects.create(
                            occurrence=det.occurrence,
                            taxon=not_identifiable_taxon,
                            user=None,  # since this comes from a post-processing algorithm  not a human
                            comment=f"Auto-set by {self.name} post-processing task",
                        )
                modified += 1
                job.logger.debug(f"Detection {det.pk}: marked as 'Not identifiable'")

        job.logger.info(f"=== Completed {self.name}: {modified}/{total} detections modified ===")

        job.result = {
            "detections_total": total,
            "detections_modified": modified,
            "threshold": threshold,
            "collection_id": collection_id,
        }
        job.save(update_fields=["result"])
