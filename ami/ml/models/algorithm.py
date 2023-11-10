from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ami.main.models import Classification

import typing

from django.db import models

from ami.base.models import BaseModel


@typing.final
class Algorithm(BaseModel):
    """A machine learning algorithm"""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    version = models.IntegerField(default=1)
    version_name = models.CharField(max_length=255, blank=True)
    url = models.URLField(blank=True)

    classfications: models.QuerySet[Classification]

    class Meta:
        ordering = ["name", "version"]

        unique_together = [
            ["name", "version"],
        ]
