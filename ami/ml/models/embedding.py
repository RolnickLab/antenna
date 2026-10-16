"""Feature vectors (embeddings) that models produce for detections, and later for captures and taxa.

Vectors are compared only within one algorithm, and each algorithm declares one vector length
(``Algorithm.embedding_dimensions``). See docs/claude/reference/feature-vectors.md.
"""

import typing

import pgvector.django
from django.db import models
from django.utils import timezone

from ami.base.models import BaseModel, BaseQuerySet
from ami.main.models import Detection

# A 2048-d vector is roughly 20 KB of SQL text (estimate), so this keeps each INSERT to a few MB.
EMBEDDING_BATCH_SIZE = 200


class BaseEmbeddingQuerySet(BaseQuerySet):
    def for_algorithm(self, algorithm_id: int):
        """The vectors of one algorithm: the only set whose vectors may be compared."""
        return self.filter(algorithm_id=algorithm_id)


class BaseEmbedding(BaseModel):
    """The columns every feature vector table shares; a subclass adds its target and its own Meta.

    Each algorithm stores at most one vector per target, and a model with several outputs registers
    one algorithm per output. The column is an unsized ``halfvec`` so that models of different lengths
    share one table. A subclass adds its target foreign key, a manager built from a
    ``BaseEmbeddingQuerySet`` subclass, and a Meta with its unique constraint and indexes.
    """

    # A subclass's own indexes lead with each of these columns, so none has a single-column index.
    algorithm = models.ForeignKey("ml.Algorithm", on_delete=models.CASCADE, related_name="%(class)ss", db_index=False)
    # The job whose results stored the vector. Deleting the job keeps the vector.
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="%(class)ss", db_index=False
    )
    # Copied from the target, so project-scoped queries need no join.
    project = models.ForeignKey("main.Project", on_delete=models.CASCADE, related_name="%(class)ss", db_index=False)
    vector = pgvector.django.HalfVectorField(help_text="The feature vector, in half precision.")
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        abstract = True


class DetectionEmbeddingQuerySet(BaseEmbeddingQuerySet):
    pass


@typing.final
class DetectionEmbedding(BaseEmbedding):
    """A feature vector for one detection, used to compare detections by appearance.

    Its project is the project of the detection's capture.
    """

    detection = models.ForeignKey(Detection, on_delete=models.CASCADE, related_name="embeddings", db_index=False)
    # Named detection_embeddings rather than the base's %(class)ss.
    algorithm = models.ForeignKey(
        "ml.Algorithm", on_delete=models.CASCADE, related_name="detection_embeddings", db_index=False
    )
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="detection_embeddings",
        db_index=False,
    )
    project = models.ForeignKey(
        "main.Project", on_delete=models.CASCADE, related_name="detection_embeddings", db_index=False
    )

    objects = DetectionEmbeddingQuerySet.as_manager()

    class Meta:
        indexes = [
            # A project's vectors from one model, in detection order, and counts per model.
            models.Index(fields=["project", "algorithm", "detection"], name="ml_detemb_proj_algo_det"),
            # One model's vectors across projects, and deleting an algorithm with its vectors.
            models.Index(fields=["algorithm", "detection"], name="ml_detemb_algo_det"),
            # A job's vectors, and clearing the job when it is deleted.
            models.Index(fields=["job", "detection"], name="ml_detemb_job_det", condition=models.Q(job__isnull=False)),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["detection", "algorithm"], name="%(app_label)s_%(class)s_unique_detection_algorithm"
            ),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} for Detection #{self.detection_id} from Algorithm #{self.algorithm_id}"


# The next vector tables follow the same pattern. Each needs its own migration, which must also set
# the vector column's storage to EXTERNAL, as ml/0031 does for detections.
#
# class SourceImageEmbedding(BaseEmbedding):
#     """A feature vector for a whole capture, for example to find similar nights or empty frames."""
#
#     source_image = models.ForeignKey(
#         "main.SourceImage", on_delete=models.CASCADE, related_name="embeddings", db_index=False
#     )
#
#     objects = BaseEmbeddingQuerySet.as_manager()
#
#     class Meta:
#         indexes = [
#             models.Index(fields=["project", "algorithm", "source_image"], name="ml_srcemb_proj_algo_src"),
#             models.Index(fields=["algorithm", "source_image"], name="ml_srcemb_algo_src"),
#             models.Index(
#                 fields=["job", "source_image"], name="ml_srcemb_job_src", condition=models.Q(job__isnull=False)
#             ),
#         ]
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["source_image", "algorithm"], name="%(app_label)s_%(class)s_unique_source_image_algorithm"
#             ),
#         ]
#
#
# class TaxonEmbedding(BaseEmbedding):
#     """A feature vector for a taxon, for example a text embedding of its name or a mean of its verified
#     detections. Its project is the project it was computed for."""
#
#     taxon = models.ForeignKey("main.Taxon", on_delete=models.CASCADE, related_name="embeddings", db_index=False)
#
#     objects = BaseEmbeddingQuerySet.as_manager()
#
#     class Meta:
#         indexes = [
#             models.Index(fields=["project", "algorithm", "taxon"], name="ml_taxemb_proj_algo_taxon"),
#             models.Index(fields=["algorithm", "taxon"], name="ml_taxemb_algo_taxon"),
#             models.Index(fields=["job", "taxon"], name="ml_taxemb_job_taxon", condition=models.Q(job__isnull=False)),
#         ]
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["taxon", "algorithm"], name="%(app_label)s_%(class)s_unique_taxon_algorithm"
#             ),
#         ]
