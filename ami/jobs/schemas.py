from django_pydantic_field.rest_framework import SchemaField
from drf_spectacular.utils import OpenApiParameter
from rest_framework import serializers

from ami.ml.schemas import PipelineTaskResult, ProcessingServiceClientInfo

ids_only_param = OpenApiParameter(
    name="ids_only",
    description="Return only job IDs instead of full objects",
    required=False,
    type=bool,
)

incomplete_only_param = OpenApiParameter(
    name="incomplete_only",
    description="Filter to only incomplete jobs (excludes jobs with final state in 'results' stage)",
    required=False,
    type=bool,
)


class TasksRequestSerializer(serializers.Serializer):
    """POST /jobs/{id}/tasks/ request body. Fetch tasks from the job queue."""

    batch_size = serializers.IntegerField(min_value=1, required=True)
    client_info = SchemaField(schema=ProcessingServiceClientInfo, required=False, default=None)


class TasksResponseSerializer(serializers.Serializer):
    """POST /jobs/{id}/tasks/ response body. Tasks returned to the processing service."""

    tasks = serializers.ListField(child=serializers.DictField(), default=[])


class PipelineResultsRequestSerializer(serializers.Serializer):
    """POST /jobs/{id}/result/ request body. Submit pipeline results for processing."""

    results = SchemaField(schema=list[PipelineTaskResult])
    client_info = SchemaField(schema=ProcessingServiceClientInfo, required=False, default=None)


class PipelineResultsResponseSerializer(serializers.Serializer):
    """POST /jobs/{id}/result/ response body. Acknowledgment of queued results."""

    status = serializers.CharField()
    job_id = serializers.IntegerField()
    results_queued = serializers.IntegerField()
    tasks = serializers.ListField(child=serializers.DictField(), default=[])
