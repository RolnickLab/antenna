from drf_spectacular.utils import OpenApiParameter
from rest_framework import serializers

from ami.ml.serializers_client_info import ClientInfoSerializer

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

batch_param = OpenApiParameter(
    name="batch",
    description="Number of tasks to retrieve",
    required=False,
    type=int,
)


class TasksRequestSerializer(serializers.Serializer):
    batch = serializers.IntegerField(min_value=1, required=True)
    client_info = ClientInfoSerializer(required=False)
