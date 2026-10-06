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


class DetectionEmbeddingQuerySet(BaseQuerySet):
    def for_algorithm(self, algorithm_id: int, key: str = DEFAULT_EMBEDDING_KEY):
        """Vectors of one kind from one algorithm: the only set whose vectors may be compared."""
        return self.filter(algorithm_id=algorithm_id, key=key)

    def store(self, embeddings) -> tuple[int, int]:
        """Write vectors insert-mostly; returns (written, unchanged).

        A (detection, algorithm, key) that already holds the same vector is left alone, so saving
        the same results twice changes nothing. One holding another vector is updated in place
        (ON CONFLICT DO UPDATE), which also keeps two writers of the same pair from losing a row.
        """
        embeddings = list(embeddings)
        if not embeddings:
            return 0, 0
        fill_embedding_project_ids(embeddings)
        stored = {
            (detection_id, algorithm_id, key): vector
            for detection_id, algorithm_id, key, vector in self.filter(
                detection_id__in={embedding.detection_id for embedding in embeddings},
                algorithm_id__in={embedding.algorithm_id for embedding in embeddings},
                key__in={embedding.key for embedding in embeddings},
            )
            .order_by()
            .values_list("detection_id", "algorithm_id", "key", "vector")
        }
        to_write = []
        for embedding in embeddings:
            existing = stored.get((embedding.detection_id, embedding.algorithm_id, embedding.key))
            if existing is None or not same_vector(existing, embedding.vector):
                to_write.append(embedding)
        if to_write:
            self.bulk_create(
                to_write,
                batch_size=EMBEDDING_BATCH_SIZE,
                update_conflicts=True,
                update_fields=["vector", "job", "timestamp", "updated_at"],
                unique_fields=["detection", "algorithm", "key"],
            )
        return len(to_write), len(embeddings) - len(to_write)


@typing.final
class DetectionEmbedding(BaseModel):
    """A feature vector for one detection, used to compare detections by appearance.

    Kept apart from classifications so every detection can have one, including those the
    moth/non-moth filter rejected, without adding a prediction that could change a
    determination. Vectors are comparable only within one (algorithm, key): ``key`` names
    the output when one model yields several, and the column is an unsized ``halfvec``
    because extractors differ in length (each algorithm keeps one, see
    ``Algorithm.embedding_dimensions``). See #1453.
    """

    # No separate index: the unique constraint's index leads with detection_id.
    detection = models.ForeignKey(Detection, on_delete=models.CASCADE, related_name="embeddings", db_index=False)
    algorithm = models.ForeignKey("ml.Algorithm", on_delete=models.CASCADE, related_name="detection_embeddings")
    # The job whose results stored the vector. Deleting the job keeps the vector.
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="detection_embeddings"
    )
    # Copied from the detection's capture (see fill_embedding_project_ids) so project queries need no join.
    project = models.ForeignKey("main.Project", on_delete=models.CASCADE, related_name="detection_embeddings")
    key = models.CharField(max_length=255, default=DEFAULT_EMBEDDING_KEY)
    vector = pgvector.django.HalfVectorField(help_text="The feature vector, in half precision.")
    timestamp = models.DateTimeField(default=timezone.now)

    objects = DetectionEmbeddingQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(check=~models.Q(key=""), name="%(app_label)s_%(class)s_key_not_empty"),
            models.UniqueConstraint(
                fields=["detection", "algorithm", "key"], name="%(app_label)s_%(class)s_unique_detection_algorithm_key"
            ),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} {self.key} for Detection #{self.detection_id} from Algorithm #{self.algorithm_id}"

    def save(self, *args, **kwargs):
        fill_embedding_project_ids([self])
        super().save(*args, **kwargs)
