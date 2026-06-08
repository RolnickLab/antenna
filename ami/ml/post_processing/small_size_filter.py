import pydantic
from django.db.models import QuerySet
from django.utils import timezone

from ami.main.models import Classification, Detection, Occurrence, SourceImageCollection, Taxon, TaxonRank
from ami.ml.post_processing.base import BasePostProcessingTask
from ami.ml.schemas import BoundingBox


class SmallSizeFilterConfig(pydantic.BaseModel):
    # Scope: exactly one of these identifies which detections to examine. A capture
    # set is the bulk path; a single occurrence is the spot/dev path (fast feedback
    # while tuning a filter). This discriminated-scope shape is the pattern other
    # post-processing tasks copy when they gain per-occurrence / per-event triggers.
    source_image_collection_id: int | None = None
    occurrence_id: int | None = None
    size_threshold: float = 0.0008

    @pydantic.validator("size_threshold")
    def _threshold_in_unit_interval(cls, v: float) -> float:
        if not (0.0 < v < 1.0):
            raise ValueError("size_threshold must be in (0, 1) exclusive")
        return v

    @pydantic.root_validator(skip_on_failure=True)
    def _exactly_one_scope(cls, values: dict) -> dict:
        scopes = [values.get("source_image_collection_id"), values.get("occurrence_id")]
        if sum(s is not None for s in scopes) != 1:
            raise ValueError("Provide exactly one of source_image_collection_id or occurrence_id")
        return values

    class Config:
        extra = "forbid"


class SmallSizeFilterTask(BasePostProcessingTask):
    key = "small_size_filter"
    name = "Small size filter"
    config_schema = SmallSizeFilterConfig

    def _scoped_detections(self, config: SmallSizeFilterConfig) -> tuple[QuerySet[Detection], str]:
        """Resolve the detections to examine from whichever scope the config carries.

        ``config_schema`` guarantees exactly one of the scope ids is set, so the
        single ``else`` branch is sound.
        """
        if config.occurrence_id is not None:
            if not Occurrence.objects.filter(pk=config.occurrence_id).exists():
                msg = f"Occurrence {config.occurrence_id} not found"
                self.logger.error(msg)
                raise ValueError(msg)
            detections = Detection.objects.filter(occurrence_id=config.occurrence_id)
            scope_desc = f"occurrence {config.occurrence_id}"
        else:
            try:
                collection = SourceImageCollection.objects.get(pk=config.source_image_collection_id)
            except SourceImageCollection.DoesNotExist:
                msg = f"SourceImageCollection {config.source_image_collection_id} not found"
                self.logger.error(msg)
                raise ValueError(msg)
            self.logger.info(f"Loaded SourceImageCollection {collection.pk} (Project={collection.project})")
            detections = Detection.objects.filter(source_image__collections=collection)
            scope_desc = f"collection {collection.pk}"
        return detections.select_related("source_image", "occurrence"), scope_desc

    def run(self) -> None:
        config: SmallSizeFilterConfig = self.config  # type: ignore[assignment]
        threshold = config.size_threshold

        # Get or create the "Not identifiable" taxon
        not_identifiable_taxon, _ = Taxon.objects.get_or_create(
            name="Not identifiable",
            defaults={
                "rank": TaxonRank.UNKNOWN,
                "notes": "Auto-generated taxon for small size filter",
            },
        )
        self.logger.info(f"=== Starting {self.name} ===")

        detections, scope_desc = self._scoped_detections(config)
        total = detections.count()
        self.logger.info(f"Found {total} detections in {scope_desc}")

        classifications_to_create: list[Classification] = []  # Can't use set until an instance has an id
        detections_to_update: set[Detection] = set()
        occcurrences_to_update: set[Occurrence] = set()
        modified_detections = 0
        modified_occurrences = 0
        checked = 0

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
                checked = i
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
                modified_occurrences += len(occcurrences_to_update)
                occcurrences_to_update.clear()

                progress = i / total if total > 0 else 1.0
                self.update_progress(progress)
                self.report_stage_metrics(
                    {
                        "detections_checked": checked,
                        "detections_flagged": modified_detections,
                        "occurrences_updated": modified_occurrences,
                    }
                )

        self.logger.info(f"=== Completed {self.name}: {modified_detections} of {total} detections modified ===")
