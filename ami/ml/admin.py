from django.contrib import admin

from ami.main.admin import AdminBase

from .models.algorithm import Algorithm
from .models.pipeline import Pipeline


@admin.register(Algorithm)
class AlgorithmAdmin(AdminBase):
    list_display = [
        "name",
        "version",
        "created_at",
    ]
    search_fields = [
        "name",
        "version",
    ]
    ordering = [
        "name",
        "version",
    ]
    list_filter = [
        "pipelines",
    ]


@admin.register(Pipeline)
class PipelineAdmin(AdminBase):
    list_display = [
        "name",
        "version",
        "created_at",
    ]
    search_fields = [
        "name",
        "version",
    ]
    from django import forms

    ordering = [
        "name",
        "version",
    ]
    list_filter = [
        "algorithms",
    ]
    filter_horizontal = [
        "algorithms",
    ]

    formfield_overrides = {
        # See https://pypi.org/project/django-json-widget/
        # models.JSONField: {"widget": JSONInput},
    }
