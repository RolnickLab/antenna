import functools
import operator
import typing
from urllib.parse import urljoin

import pydantic

from ami.main.models import DEFAULT_EMBEDDING_KEY, Detection, SourceImageCollection
from ami.ml.embeddings.reader import detections_missing_vectors
from ami.ml.embeddings.writer import save_embedding_results
from ami.ml.exceptions import PipelineNotConfigured
from ami.ml.models import Pipeline
from ami.ml.models.pipeline import process_detections
from ami.ml.post_processing.base import BasePostProcessingTask


class AddFeatureVectorsConfig(pydantic.BaseModel):
    source_image_collection_id: int
    pipeline_id: int
    key: str = DEFAULT_EMBEDDING_KEY
    # Captures per request. Each request carries every missing detection of its captures.
    batch_size: int = pydantic.Field(default=10, ge=1, le=100)

    class Config:
        extra = "forbid"


class AddFeatureVectorsTask(BasePostProcessingTask):
    """Add feature vectors to detections that already exist, without detecting or classifying again.

    For the captures of one capture set, sends only the valid detections that lack a vector from
    the pipeline's feature extractor to the processing service, and stores the returned vectors
    on those detections. Running it twice sends nothing the second time.
    """

    key = "add_feature_vectors"
    name = "Add feature vectors"
    config_schema = AddFeatureVectorsConfig

    def _missing_detections(self, collection: SourceImageCollection, pipeline: Pipeline, key: str):
        """Valid detections of the capture set that lack a vector from any of the pipeline's extractors."""
        detections = Detection.objects.valid().filter(source_image__collections=collection)
        return functools.reduce(
            operator.or_,
            (
                detections_missing_vectors(detections, extractor.pk, key)
                for extractor in pipeline.embedding_algorithms()
            ),
        )

    def run(self) -> None:
        config = typing.cast(AddFeatureVectorsConfig, self.config)
        try:
            collection = SourceImageCollection.objects.get(pk=config.source_image_collection_id)
            pipeline = Pipeline.objects.get(pk=config.pipeline_id)
        except (SourceImageCollection.DoesNotExist, Pipeline.DoesNotExist) as err:
            self.logger.error(str(err))
            raise ValueError(str(err)) from err
        if not pipeline.embedding_algorithms().exists():
            msg = f'Pipeline "{pipeline.name}" has no algorithm that produces feature vectors (task type "embedding").'
            self.logger.error(msg)
            raise ValueError(msg)

        missing = self._missing_detections(collection, pipeline, config.key)
        capture_ids = sorted(missing.order_by().values_list("source_image_id", flat=True).distinct())
        self.logger.info(
            f"=== Starting {self.name}: {len(capture_ids)} captures of capture set {collection.pk} "
            f"have detections without a vector from pipeline {pipeline} ==="
        )

        if not capture_ids:
            self.logger.info(f"=== Completed {self.name}: nothing to add ===")
            return
        processing_service = pipeline.choose_processing_service_for_pipeline(
            self.job.pk if self.job else None, pipeline.name, collection.project_id
        )
        if not processing_service.endpoint_url:
            raise PipelineNotConfigured(
                f"No endpoint URL configured for this pipeline's processing service ({processing_service})"
            )
        endpoint_url = urljoin(processing_service.endpoint_url, "/process")

        totals = {
            "Captures": 0,
            "Detections sent": 0,
            "Vectors stored": 0,
            "Vectors unchanged": 0,
            "Boxes unmatched": 0,
        }
        self.report_stage_metrics(totals)
        for start in range(0, len(capture_ids), config.batch_size):
            batch = list(
                missing.filter(source_image_id__in=capture_ids[start : start + config.batch_size])
                .select_related("source_image__deployment__data_source", "detection_algorithm")
                .order_by("source_image_id", "pk")
            )
            response = process_detections(pipeline, endpoint_url, batch, collection.project_id)
            result = save_embedding_results(response, self.job, pipeline, config.key)
            totals["Captures"] += len({detection.source_image_id for detection in batch})
            totals["Detections sent"] += len(batch)
            totals["Vectors stored"] += result.written
            totals["Vectors unchanged"] += result.unchanged
            totals["Boxes unmatched"] += result.unmatched
            self.update_progress(min(start + config.batch_size, len(capture_ids)) / len(capture_ids))
            self.report_stage_metrics(totals)

        self.logger.info(f"=== Completed {self.name}: {totals} ===")
