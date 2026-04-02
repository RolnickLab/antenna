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


class MLJobTasksRequestSerializer(serializers.Serializer):
    """POST /jobs/{id}/tasks/ — request body sent by a processing service to fetch work.

    The processing service polls this endpoint to get tasks (images) to process.
    Each task is a PipelineProcessingTask with an image URL and a NATS reply subject.
    """

    batch_size = serializers.IntegerField(min_value=1, required=True)
    client_info = SchemaField(schema=ProcessingServiceClientInfo, required=False, default=None)


class MLJobTasksResponseSerializer(serializers.Serializer):
    """POST /jobs/{id}/tasks/ — response body returned to the processing service.

    Contains a list of tasks (PipelineProcessingTask dicts) for the worker to process.
    Each task includes an image URL, task ID, and reply_subject for result correlation.
    Returns an empty list when no tasks are available or the job is not active.
    """

    tasks = serializers.ListField(child=serializers.DictField(), default=[])


class MLJobResultsRequestSerializer(serializers.Serializer):
    """POST /jobs/{id}/result/ — request body sent by a processing service to deliver results.

    "Request" here refers to the HTTP request to Antenna, not a request for work.
    The processing service has finished processing tasks and is posting its results
    (successes or errors) back. Each PipelineTaskResult contains a reply_subject
    (correlating back to the original task) and a result payload that is either a
    PipelineResultsResponse (success) or PipelineResultsError (failure).
    """

    results = SchemaField(schema=list[PipelineTaskResult])
    client_info = SchemaField(schema=ProcessingServiceClientInfo, required=False, default=None)


class MLJobResultsResponseSerializer(serializers.Serializer):
    """POST /jobs/{id}/result/ — acknowledgment returned to the processing service.

    Confirms receipt and indicates how many results were queued for background
    processing via Celery. Individual task entries include their Celery task_id
    for traceability.
    """

    status = serializers.CharField()
    job_id = serializers.IntegerField()
    results_queued = serializers.IntegerField()
    tasks = serializers.ListField(child=serializers.DictField(), default=[])
