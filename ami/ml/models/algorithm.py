from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ami.main.models import Classification
    from ami.ml.models import Pipeline

import typing

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.text import slugify

from ami.base.models import BaseModel


@typing.final
class Algorithm(BaseModel):
    """A machine learning algorithm"""

    name = models.CharField(max_length=255)
    key = models.SlugField(max_length=255, unique=True)
    task_type = models.CharField(
        max_length=255,
        blank=True,
        choices=[
            ("detection", "Detection"),
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
            ("other", "Other"),
        ],
    )
    description = models.TextField(blank=True)
    version = models.IntegerField(
        default=1, help_text="An internal, sortable and incrementable version number for the model."
    )
    version_name = models.CharField(max_length=255, blank=True)
    url = models.URLField(blank=True)  # URL to the model homepage, origin or docs (huggingface, wandb, etc.)
    category_map = models.ForeignKey(
        "AlgorithmCategoryMap",
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

    class Meta:
        ordering = ["name", "version"]

        unique_together = [
            ["name", "version"],
        ]

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = slugify(self.name)
        super().save(*args, **kwargs)


class AlgorithmCategoryMap(BaseModel):
    """
    A list of classification labels for a given algorithm version
    """

    data = models.JSONField(
        help_text="Complete metadata for each label, such as id, gbif_key, explicit index, source, etc."
    )
    labels = ArrayField(
        models.CharField(max_length=255),
        default=list,
        help_text="A simple list of string labels in the correct index order used by the model.",
    )
    version = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    url = models.URLField(blank=True, null=True)

    algorithms: models.QuerySet[Algorithm]

    def get_category(self, label, label_field="label"):
        # Can use JSON containment operators
        return self.data.index(next(category for category in self.data if category[label_field] == label))

    def with_taxa(self, category_field="label"):
        """
        Add Taxon objects to the category map, or None if no match

        :param category_field: The field in the category data to match against the Taxon name
        :return: The category map with the taxon objects added

        @TODO consider creating missing taxa
        """

        from ami.main.models import Taxon

        taxa = Taxon.objects.filter(models.Q(name__in=self.labels) | models.Q(search_names__overlap=self.labels))
        taxon_map = {taxon.name: taxon for taxon in taxa}

        for category in self.data:
            taxon = taxon_map.get(category[category_field])
            category["taxon"] = taxon

        return self.data
