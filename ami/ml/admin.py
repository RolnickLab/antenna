from django.contrib import admin

from ami.main.admin import AdminBase, ProjectPipelineConfigInline

from .models.algorithm import Algorithm, AlgorithmCategoryMap
from .models.algorithm_result import AlgorithmResult
from .models.embedding import DetectionEmbedding, VectorDims
from .models.pipeline import Pipeline
from .models.processing_service import ProcessingService


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


@admin.register(AlgorithmResult)
class AlgorithmResultAdmin(AdminBase):
    """Read-only: results are written by their runs through the writer, which validates them."""

    # Ids rather than the occurrence's name, which would join its deployment and determination per row.
    list_display = ["id", "kind", "value", "occurrence_id", "algorithm", "job", "project", "timestamp"]
    list_filter = ["kind", "algorithm", "project"]
    list_select_related = ["algorithm", "job", "project"]
    search_fields = ["=occurrence__id", "=job__id"]
    ordering = ["-timestamp", "-pk"]
    raw_id_fields = ["occurrence", "job"]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


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
        "created_at",
    ]


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


@admin.register(DetectionEmbedding)
class DetectionEmbeddingAdmin(admin.ModelAdmin):
    """Read-only view of stored feature vectors: the vector is never loaded, only its length."""

    list_display = ["id", "detection_id", "algorithm", "key", "vector_length", "job", "project", "timestamp"]
    list_select_related = ["algorithm", "job", "project"]
    list_filter = ["algorithm"]
    raw_id_fields = ["detection"]
    fields = ("detection", "algorithm", "key", "vector_length", "job", "project", "timestamp")
    readonly_fields = fields
    ordering = ["-id"]
    show_full_result_count = False

    def get_queryset(self, request):
        return super().get_queryset(request).defer("vector").annotate(vector_length=VectorDims("vector"))

    @admin.display(description="Vector length")
    def vector_length(self, obj: DetectionEmbedding) -> int:
        return obj.vector_length  # type: ignore[attr-defined] # Annotated in get_queryset

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
