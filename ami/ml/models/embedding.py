"""Feature vectors for detections, stored next to the other model outputs in the ml app."""

import typing

import numpy as np
import pgvector
import pgvector.django
from django.db import models
from django.utils import timezone

from ami.base.models import BaseModel, BaseQuerySet
from ami.main.models import DEFAULT_EMBEDDING_KEY, Detection

# A 2048-d vector is roughly 20 KB of SQL text (estimate), so this keeps each INSERT to a few MB.
EMBEDDING_BATCH_SIZE = 200


class VectorDims(models.Func):
    """pgvector's ``vector_dims()``: the length of a vector or halfvec value."""

    function = "vector_dims"
    output_field = models.IntegerField()


def as_half_precision(vector) -> np.ndarray:
    """A vector as the half-precision array the ``halfvec`` column stores."""
    if isinstance(vector, pgvector.HalfVector):
        return vector.to_numpy()
    # A value beyond half precision's range becomes infinity, which the writer then refuses.
    with np.errstate(over="ignore"):
        return np.asarray(vector, dtype=np.float16)


def same_vector(stored, new) -> bool:
    return bool(np.array_equal(as_half_precision(stored), as_half_precision(new)))


def fill_embedding_project_ids(embeddings: list["DetectionEmbedding"]) -> None:
    """Give each vector without a project its detection's capture's project, or the capture's station's.

    Raises ``ValueError`` when neither has one: a vector must always be reachable by project.
    """
    missing = [embedding for embedding in embeddings if embedding.project_id is None]
    if not missing:
        return
    projects = {
        detection_id: capture_project_id or station_project_id
        for detection_id, capture_project_id, station_project_id in Detection.objects.filter(
            pk__in={embedding.detection_id for embedding in missing}
        ).values_list("pk", "source_image__project_id", "source_image__deployment__project_id")
    }
    for embedding in missing:
        embedding.project_id = projects.get(embedding.detection_id)
        if embedding.project_id is None:
            raise ValueError(
                f"Detection #{embedding.detection_id} belongs to no project: neither its capture nor its "
                "station has one, so its feature vector cannot be stored."
            )


class BaseEmbeddingQuerySet(BaseQuerySet):
    """Reading and writing the vectors of one kind of target (detections, captures, taxa).

    A subclass names its target foreign key in ``target_field``; everything else is shared.
    """

    target_field: typing.ClassVar[str]

    def for_algorithm(self, algorithm_id: int, key: str = DEFAULT_EMBEDDING_KEY):
        """Vectors of one kind from one algorithm: the only set whose vectors may be compared."""
        return self.filter(algorithm_id=algorithm_id, key=key)

    def stored_length(self, algorithm_id: int, key: str = DEFAULT_EMBEDDING_KEY) -> int | None:
        """The length of the vectors already stored for one (algorithm, key), or None when there are none.

        Reads the first row of the pair (an indexed lookup on (algorithm, key, target) whether or not
        the pair has rows), so a writer can hold each pair to one length without a stored field. The
        ``order_by`` is what lets the planner walk that index instead of scanning the table until a row matches.
        """
        rows = (
            self.for_algorithm(algorithm_id, key)
            .order_by(f"{self.target_field}_id")
            .annotate(dims=VectorDims("vector"))
            .values_list("dims", flat=True)[:1]
        )
        return next(iter(rows), None)

    def store(self, embeddings) -> tuple[int, int]:
        """Write vectors insert-mostly; returns (written, unchanged).

        A (target, algorithm, key) that already holds the same vector is left alone, so saving
        the same results twice changes nothing. One holding another vector is updated in place
        (ON CONFLICT DO UPDATE), which also keeps two writers of the same pair from losing a row.
        """
        embeddings = list(embeddings)
        if not embeddings:
            return 0, 0
        target_id = f"{self.target_field}_id"
        self.model.fill_project_ids(embeddings)
        stored = {
            (target, algorithm_id, key): vector
            for target, algorithm_id, key, vector in self.filter(
                **{
                    f"{target_id}__in": {getattr(embedding, target_id) for embedding in embeddings},
                    "algorithm_id__in": {embedding.algorithm_id for embedding in embeddings},
                    "key__in": {embedding.key for embedding in embeddings},
                }
            )
            .order_by()
            .values_list(target_id, "algorithm_id", "key", "vector")
        }
        to_write = []
        for embedding in embeddings:
            existing = stored.get((getattr(embedding, target_id), embedding.algorithm_id, embedding.key))
            if existing is None or not same_vector(existing, embedding.vector):
                to_write.append(embedding)
        if to_write:
            self.bulk_create(
                to_write,
                batch_size=EMBEDDING_BATCH_SIZE,
                update_conflicts=True,
                update_fields=["vector", "job", "timestamp", "updated_at"],
                unique_fields=[self.target_field, "algorithm", "key"],
            )
        return len(to_write), len(embeddings) - len(to_write)


class DetectionEmbeddingQuerySet(BaseEmbeddingQuerySet):
    target_field = "detection"


class BaseEmbedding(BaseModel):
    """The columns every kind of feature vector table shares; a subclass adds its target and its own Meta.

    Vectors are comparable only within one (algorithm, key): ``key`` names the output when one
    model yields several, and the column is an unsized ``halfvec`` because extractors differ in
    length. Each (algorithm, key) keeps one length, enforced by the writer against an existing row.
    A subclass adds its target foreign key, a ``fill_project_ids`` classmethod, a manager built
    from a ``BaseEmbeddingQuerySet`` subclass, and a Meta with its own unique constraint and
    indexes (see docs/claude/reference/feature-vectors.md, "Adding a sibling table").
    """

    # None of the foreign keys has a single-column index of its own: a subclass's unique constraint
    # leads with its target, and its Meta indexes lead with algorithm, project and job. Extra
    # single-column indexes would only cost writes and mislead the planner.
    algorithm = models.ForeignKey("ml.Algorithm", on_delete=models.CASCADE, related_name="%(class)ss", db_index=False)
    # The job whose results stored the vector. Deleting the job keeps the vector.
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="%(class)ss", db_index=False
    )
    project = models.ForeignKey("main.Project", on_delete=models.CASCADE, related_name="%(class)ss", db_index=False)
    key = models.CharField(max_length=255, default=DEFAULT_EMBEDDING_KEY)
    vector = pgvector.django.HalfVectorField(help_text="The feature vector, in half precision.")
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        abstract = True

    @classmethod
    def fill_project_ids(cls, embeddings: list) -> None:
        """Give each vector without a project the project of its target; raise ``ValueError`` if it has none."""
        raise NotImplementedError

    def save(self, *args, **kwargs):
        self.fill_project_ids([self])
        super().save(*args, **kwargs)


@typing.final
class DetectionEmbedding(BaseEmbedding):
    """A feature vector for one detection, used to compare detections by appearance.

    Kept apart from classifications so every detection can have one, including those the
    moth/non-moth filter rejected, without adding a prediction that could change a
    determination. See #1462 and ``BaseEmbedding``.
    """

    detection = models.ForeignKey(Detection, on_delete=models.CASCADE, related_name="embeddings", db_index=False)
    # Related names that predate the shared base keep their original spelling.
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
    # Copied from the detection's capture (see fill_embedding_project_ids) so project queries need no join.
    project = models.ForeignKey(
        "main.Project", on_delete=models.CASCADE, related_name="detection_embeddings", db_index=False
    )

    objects = DetectionEmbeddingQuerySet.as_manager()

    class Meta:
        indexes = [
            # Project-scoped reads of one model: a project's vectors in detection order, and counts per model.
            models.Index(fields=["project", "algorithm", "key", "detection"], name="ml_detemb_proj_algo_key_det"),
            # The writer's per-model length lookup: the first row of a pair, by detection, with or without rows.
            models.Index(fields=["algorithm", "key", "detection"], name="ml_detemb_algo_key"),
            # "Occurrences this job touched" looks up a job's vectors by job, then detection.
            models.Index(fields=["job", "detection"], name="ml_detemb_job_det", condition=models.Q(job__isnull=False)),
        ]
        constraints = [
            models.CheckConstraint(check=~models.Q(key=""), name="%(app_label)s_%(class)s_key_not_empty"),
            models.UniqueConstraint(
                fields=["detection", "algorithm", "key"], name="%(app_label)s_%(class)s_unique_detection_algorithm_key"
            ),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} {self.key} for Detection #{self.detection_id} from Algorithm #{self.algorithm_id}"

    @classmethod
    def fill_project_ids(cls, embeddings: list["DetectionEmbedding"]) -> None:
        fill_embedding_project_ids(embeddings)
