from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ami.main.models import Classification
    from ami.ml.models import Pipeline

import typing

from django.db import models
from django.utils.text import slugify

from ami.base.models import BaseModel


@typing.final
class Algorithm(BaseModel):
    """A machine learning algorithm"""

    name = models.CharField(max_length=255)
    key = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    version = models.IntegerField(default=1)
    version_name = models.CharField(max_length=255, blank=True)
    url = models.URLField(blank=True)  # URL to the model homepage, origin or docs (huggingface, wandb, etc.)

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
