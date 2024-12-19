from django.contrib import admin

from ami.main.admin import AdminBase

from .models.algorithm import Algorithm
from .models.backend import Backend
from .models.pipeline import Pipeline


@admin.register(Algorithm)
class AlgorithmAdmin(AdminBase):
    list_display = [
        "name",
        "version",
        "version_name",
        "created_at",
        "updated_at",
    ]
    search_fields = [
        "name",
        "version_name",
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
        "version_name",
        "created_at",
    ]
    search_fields = [
        "name",
        "version_name",
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


@admin.register(Backend)
class BackendAdmin(AdminBase):
    list_display = [
        "id",
        "name",
        "endpoint_url",
        "created_at",
    ]
