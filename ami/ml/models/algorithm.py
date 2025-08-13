from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ami.main.models import Classification, Taxon
    from ami.ml.models import Pipeline

import logging
import typing

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.text import slugify

from ami.base.models import BaseModel

logger = logging.getLogger(__name__)


@typing.final
class AlgorithmCategoryMap(BaseModel):
    """
    A list of classification labels for a given algorithm version
    """

    data = models.JSONField(
        help_text="Complete metadata for each label, such as id, gbif_key, lookup value, source, etc."
    )
    labels = ArrayField(
        models.CharField(max_length=255),
        default=list,
        help_text="A simple list of string labels in the correct index order used by the model.",
    )
    labels_hash = models.BigIntegerField(
        help_text="A hash of the labels for faster comparison of label sets. Created on save.",
        null=True,
    )
    version = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    uri = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=("A URI to the category map file. " "Could be a public web URL or object store path."),
    )

    algorithms: models.QuerySet[Algorithm]

    def __str__(self):
        return f"#{self.pk} with {len(self.labels)} classes ({self.version or 'unknown version'})"

    @classmethod
    def make_labels_hash(cls, labels):
        """
        Create a hash from the labels for faster comparison of unique label sets
        """
        return hash("".join(labels))

    def get_category(self, label, label_field="label"):
        # Can use JSON containment operators
        return self.data.index(next(category for category in self.data if category[label_field] == label))

    def with_taxa(
        self, category_field="label", only_indexes: list[int] | None = None
    ) -> list[dict[str, str | int | Taxon | None]]:
        """
        Add Taxon objects to the category map, or None if no match

        :param category_field: The field in the category data to match against the Taxon name
        :return: The category map with the taxon objects added

        @TODO need a top_n parameter to limit the number of taxa to fetch
        @TODO consider creating missing taxa?
        """

        from ami.main.models import Taxon, TaxonRank

        if only_indexes:
            labels_data = [self.data[i] for i in only_indexes]
            labels_label = [self.labels[i] for i in only_indexes]
        else:
            labels_data = self.data
            labels_label = self.labels

        # @TODO standardize species search / lookup.
        # See similar query in ml.models.pipeline.get_or_create_taxon_for_classification()
        taxa = Taxon.objects.filter(
            models.Q(name__in=labels_label) | models.Q(search_names__overlap=labels_label),
            active=True,
        )
        taxon_map = {taxon.name: taxon for taxon in taxa}

        for category in labels_data:
            taxon = taxon_map.get(category[category_field])
            # Import all taxa in the category map that are not in the database yet
            if not taxon:
                taxon = Taxon.objects.create(
                    name=category["label"],
                    rank=category.get("taxon_rank", TaxonRank.SPECIES),  # @TODO: make this flexible
                )
                # @TODO: this doesn't seem to be working - logging works but no species are registered
                logger.info(f"Registered new taxon {taxon}")
            category["taxon"] = taxon

        return labels_data

    def save(self, *args, **kwargs):
        if not self.labels_hash:
            self.labels_hash = self.make_labels_hash(self.labels)
        super().save(*args, **kwargs)


class ArrayLength(models.Func):
    function = "CARDINALITY"


class AlgorithmQuerySet(models.QuerySet["Algorithm"]):
    def with_category_count(self):
        """
        Annotate the queryset with the number of categories in the category map
        """
        return self.annotate(category_count=ArrayLength("category_map__labels"))


@typing.final
class Algorithm(BaseModel):
    """A machine learning algorithm"""

    name = models.CharField(max_length=255)
    key = models.SlugField(max_length=255, unique=True)
    task_type = models.CharField(
        max_length=255,
        default="unknown",
        null=True,
        choices=[
            ("detection", "Detection"),
            ("localization", "Localization"),
            ("segmentation", "Segmentation"),
            ("classification", "Classification"),
            ("embedding", "Embedding"),
            ("tracking", "Tracking"),
            ("tagging", "Tagging"),
            ("regression", "Regression"),
            ("captioning", "Captioning"),
            ("generation", "Generation"),
            ("translation", "Translation"),
            ("summarization", "Summarization"),
            ("question_answering", "Question Answering"),
            ("depth_estimation", "Depth Estimation"),
            ("pose_estimation", "Pose Estimation"),
            ("size_estimation", "Size Estimation"),
            ("clustering", "Clustering"),
            ("other", "Other"),
            ("unknown", "Unknown"),
        ],
    )
    detection_algorithm_task_types = ["detection", "localization", "segmentation"]
    description = models.TextField(blank=True)
    version = models.IntegerField(
        default=1,
        help_text="An internal, sortable and incrementable version number for the model.",
    )
    version_name = models.CharField(max_length=255, blank=True, null=True)
    uri = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=("A URI to the weights or model details. Could be a public web URL or object store path."),
    )

    category_map = models.ForeignKey(
        AlgorithmCategoryMap,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="algorithms",
        default=None,
    )

    # api_base_url = models.URLField(blank=True)
    # api = models.CharField(max_length=255, blank=True)

    pipelines: models.QuerySet[Pipeline]
    classifications: models.QuerySet[Classification]

    objects = AlgorithmQuerySet.as_manager()

    def __str__(self):
        return f'#{self.pk} "{self.name}" ({self.key}) v{self.version}'

    class Meta:
        ordering = ["name", "version"]

        unique_together = [
            ["name", "version"],
        ]

    def save(self, *args, **kwargs):
        if not self.version_name:
            self.version_name = f"{self.version}"
        if not self.key:
            self.key = f"{slugify(self.name)}-{self.version}"
        super().save(*args, **kwargs)

    def category_count(self) -> int | None:
        """
        Return the number of classes in the category map, if applicable and available.

        This must be retrieved using the QuerySet method with_category_count()
        but is defined here for the serializer to work.
        """
        return None
