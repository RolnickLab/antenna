from django.contrib import admin
from rest_framework_api_key.admin import APIKeyModelAdmin

from ami.main.admin import AdminBase, ProjectPipelineConfigInline

from .models.algorithm import Algorithm, AlgorithmCategoryMap
from .models.pipeline import Pipeline
from .models.processing_service import ProcessingService, ProcessingServiceAPIKey


@admin.register(Algorithm)
class AlgorithmAdmin(AdminBase):
    list_display = [
        "name",
        "key",
        "version",
        "version_name",
        "task_type",
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
        "task_type",
    ]


@admin.register(Pipeline)
class PipelineAdmin(AdminBase):
    inlines = [ProjectPipelineConfigInline]
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


@admin.register(ProcessingService)
class ProcessingServiceAdmin(AdminBase):
    list_display = [
        "id",
        "name",
        "endpoint_url",
        "last_seen_live",
        "created_at",
    ]
    readonly_fields = ["last_seen_client_info"]

    @admin.action(description="Generate API key for selected processing services (revokes existing)")
    def generate_api_key(self, request, queryset):
        for ps in queryset:
            ps.api_keys.filter(revoked=False).update(revoked=True)
            _, plaintext_key = ProcessingServiceAPIKey.objects.create_key(
                name=f"{ps.name} key",
                processing_service=ps,
            )
            self.message_user(
                request,
                f"{ps.name}: {plaintext_key} (copy now — it won't be shown again)",
            )

    actions = [generate_api_key]


@admin.register(ProcessingServiceAPIKey)
class ProcessingServiceAPIKeyAdmin(APIKeyModelAdmin):
    list_display = [*APIKeyModelAdmin.list_display, "processing_service"]
    list_filter = ["processing_service"]
    search_fields = [*APIKeyModelAdmin.search_fields, "processing_service__name"]


@admin.register(AlgorithmCategoryMap)
class AlgorithmCategoryMapAdmin(AdminBase):
    list_display = [
        "version",
        "uri",
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
    formfield_overrides = {
        # See https://pypi.org/project/django-json-widget/
        # models.JSONField: {"widget": JSONInput},
    }

    def num_data_items(self, obj):
        return len(obj.data) if obj.data else 0

    def num_labels(self, obj):
        return len(obj.labels) if obj.labels else 0
