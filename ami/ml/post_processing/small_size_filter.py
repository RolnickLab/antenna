from django.utils import timezone

from ami.main.models import Classification, Detection, Occurrence, SourceImageCollection, Taxon, TaxonRank
from ami.ml.post_processing.base import BasePostProcessingTask
from ami.ml.schemas import BoundingBox


class SmallSizeFilterTask(BasePostProcessingTask):
    key = "small_size_filter"
    name = "Small size filter"

    def run(self) -> None:
        # Could we use a pydantic model for config validation if it's just for this task?
        threshold = self.config.get("size_threshold", 0.0008)
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

        detections = Detection.objects.filter(source_image__collections=collection).select_related(
            "source_image", "occurrence"
        )
        total = detections.count()
        self.logger.info(f"Found {total} detections in collection {collection_id}")

        classifications_to_create: list[Classification] = []  # Can't use set until an instance has an id
        detections_to_update: set[Detection] = set()
        occcurrences_to_update: set[Occurrence] = set()
        modified_detections = 0

        for i, det in enumerate(detections.iterator(), start=1):
            bbox = det.get_bbox()
            if not bbox:
                self.logger.debug(f"Detection {det.pk}: no bbox, skipping")
                continue

            img_w, img_h = det.source_image.width, det.source_image.height
            if not img_w or not img_h:
                self.logger.debug(f"Detection {det.pk}: missing source image dims, skipping")
                continue

            bbox_obj = BoundingBox.from_coords(det.bbox, raise_on_error=False)
            if not bbox_obj:
                self.logger.warning(f"Detection {det.pk}: invalid bbox, skipping")
                continue
            det_w, det_h = bbox_obj.width, bbox_obj.height
            det_area = det_w * det_h
            img_area = img_w * img_h
            rel_area = det_area / img_area if img_area else 0

            self.logger.debug(
                f"Detection {det.pk}: area={det_area}, rel_area={rel_area:.4f}, " f"threshold={threshold:.4f}"
            )

            if rel_area < threshold:
                # Create the new "Not identifiable" classification
                classifications_to_create.append(
                    Classification(
                        detection=det,
                        taxon=not_identifiable_taxon,
                        score=1.0,
                        terminal=True,
                        timestamp=timezone.now(),  # How is this different from created_at?
                        algorithm=self.algorithm,
                        applied_to=None,  # Size filter is applied to original detection, not a previous classification
                    )
                )
                detections_to_update.add(det)
                if det.occurrence is not None:
                    occcurrences_to_update.add(det.occurrence)
                self.logger.debug(f"Marking detection {det.pk} as {not_identifiable_taxon.name}")

            # Update progress every 100 detections
            if i % 100 == 0 or i == total:
                modified_detections += len(detections_to_update)

                # with transaction.atomic():
                self.logger.info(f"Creating {len(classifications_to_create)} new classifications")
                Classification.objects.bulk_create(classifications_to_create)
                classifications_to_create.clear()

                self.logger.info(f"Marking {len(detections_to_update)} detections as {not_identifiable_taxon.name}")
                for det in detections_to_update:
                    det.updated_at = timezone.now()
                Detection.objects.bulk_update(detections_to_update, ["updated_at"])
                detections_to_update.clear()

                self.logger.info(f"Updating {len(occcurrences_to_update)} occurrences")
                for occ in occcurrences_to_update:
                    occ.save(update_determination=True)
                occcurrences_to_update.clear()

                progress = i / total if total > 0 else 1.0
                self.update_progress(progress)

        self.logger.info(f"=== Completed {self.name}: {modified_detections} of {total} detections modified ===")
