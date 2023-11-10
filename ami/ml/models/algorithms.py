import typing

from django.db import models

from ami.main.models import BaseModel, Classification


@typing.final
class Algorithm(BaseModel):
    """A machine learning algorithm"""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    version = models.CharField(max_length=255, blank=True)
    url = models.URLField(blank=True)

    classfications: models.QuerySet["Classification"]
