from django.contrib import admin

from ami.main.admin import AdminBase

from .models.algorithm import Algorithm, AlgorithmCategoryMap
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


@admin.register(AlgorithmCategoryMap)
class AlgorithmCategoryMapAdmin(AdminBase):
    list_display = [
        "version",
        "url",
        "created_at",
        "num_data_items",
        "num_labels",
    ]
    search_fields = [
        "version",
    ]
    ordering = [
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

    def num_data_items(self, obj):
        return len(obj.data) if obj.data else 0

    def num_labels(self, obj):
        return len(obj.labels) if obj.labels else 0
