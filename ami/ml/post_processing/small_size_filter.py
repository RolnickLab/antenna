from django.db import transaction
from django.utils import timezone

from ami.main.models import Detection, SourceImageCollection, Taxon, TaxonRank
from ami.ml.post_processing.base import BasePostProcessingTask


class SmallSizeFilterTask(BasePostProcessingTask):
    key = "small_size_filter"
    name = "Small size filter"

    def run(self) -> None:
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
        self.logger.info(f"=== Starting {self.name} ===")

        if not collection_id:
            msg = "Missing required config param: source_image_collection_id"
            self.logger.error(msg)
            raise ValueError(msg)

        try:
            collection = SourceImageCollection.objects.get(pk=collection_id)
            self.logger.info(f"Loaded SourceImageCollection {collection_id} (Project={collection.project})")
        except SourceImageCollection.DoesNotExist:
            msg = f"SourceImageCollection {collection_id} not found"
            self.logger.error(msg)
            raise ValueError(msg)

        detections = Detection.objects.filter(source_image__collections=collection)
        total = detections.count()
        self.logger.info(f"Found {total} detections in collection {collection_id}")

        modified = 0

        for i, det in enumerate(detections.iterator(), start=1):
            bbox = det.get_bbox()
            if not bbox:
                self.logger.debug(f"Detection {det.pk}: no bbox, skipping")
                continue

            img_w, img_h = det.source_image.width, det.source_image.height
            if not img_w or not img_h:
                self.logger.debug(f"Detection {det.pk}: missing source image dims, skipping")
                continue

            det_w, det_h = det.width(), det.height()
            if not det_w or not det_h:
                self.logger.warning(f"Detection {det.pk}: invalid bbox dims (width={det_w}, height={det_h}), skipping")
                continue
            det_area = det_w * det_h
            img_area = img_w * img_h
            rel_area = det_area / img_area if img_area else 0

            self.logger.info(
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
                    occurrence = det.occurrence
                    occurrence.save(update_determination=True)
                modified += 1
                self.logger.info(f"Detection {det.pk}: marked as 'Not identifiable'")

            # Update progress every 10 detections
            if i % 10 == 0 or i == total:
                progress = i / total if total > 0 else 1.0
                self.update_progress(progress)

        self.logger.info(f"=== Completed {self.name}: {modified}/{total} detections modified ===")
