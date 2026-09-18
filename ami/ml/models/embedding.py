import logging

from django.db import models
from pgvector.django import HalfVectorField

from ami.base.models import BaseModel

logger = logging.getLogger(__name__)

# Width of the vectors this table holds. BioCLIP 2.5 (ViT-H/14) emits 1024 dimensions.
# pgvector needs a fixed width per column in order to index it, so a backbone with a
# different width (BioCLIP 2 ViT-L/14 is 768) needs its own column or its own table.
EMBEDDING_DIMENSIONS = 1024


class DetectionEmbedding(BaseModel):
    """
    The feature vector a classifier's backbone produced for one detection crop.

    The backbone is frozen, so a crop's embedding never changes. Storing it lets a
    classifier head be retrained from verified labels without re-running the backbone.

    Kept off Detection deliberately: the vector is ~2 KB, Detection is scanned constantly
    by the list views, and Postgres would TOAST a column that wide anyway.
    """

    project_accessor = "detection__source_image__project"

    detection = models.ForeignKey(
        "main.Detection",
        on_delete=models.CASCADE,
        related_name="embeddings",
    )
    algorithm = models.ForeignKey(
        "ml.Algorithm",
        on_delete=models.CASCADE,
        related_name="embeddings",
        help_text=(
            "The algorithm whose backbone produced this vector. Vectors from different "
            "algorithms live in different spaces and must never be compared to each other."
        ),
    )
    # halfvec (2 bytes/dim) rather than vector (4). Measured at 20k rows, a row plus its
    # share of the HNSW index costs ~5 KB; float32 would roughly double that.
    vector = HalfVectorField(dimensions=EMBEDDING_DIMENSIONS)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["detection", "algorithm"],
                name="unique_embedding_per_detection_and_algorithm",
            )
        ]
        # Deliberately no vector index. These are read in bulk to train a head, never
        # searched by nearest neighbour, and an HNSW index measured at roughly the size of
        # the rows themselves (45 MB against 54 MB at 20k rows). Add one if similarity
        # search is ever wanted; it can be built on the existing data.

    def __str__(self) -> str:
        return f"Embedding of Detection #{self.detection_id} by {self.algorithm}"
