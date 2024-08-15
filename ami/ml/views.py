import logging

from rest_framework.views import APIView, Response, status

from ami.main.api.views import DefaultViewSet
from ami.ml.models.pipeline import PipelineAsyncRequestRecord, PipelineAsyncRequestStatus

from .models.algorithm import Algorithm
from .models.pipeline import Pipeline
from .serializers import AlgorithmSerializer, PipelineSerializer

logger = logging.getLogger(__name__)


class AlgorithmViewSet(DefaultViewSet):
    """
    API endpoint that allows algorithm (ML models) to be viewed or edited.
    """

    queryset = Algorithm.objects.all()
    serializer_class = AlgorithmSerializer
    filterset_fields = ["name", "version"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "name",
        "version",
    ]
    search_fields = ["name"]


class PipelineViewSet(DefaultViewSet):
    """
    API endpoint that allows pipelines to be viewed or edited.
    """

    queryset = Pipeline.objects.prefetch_related("algorithms").all()
    serializer_class = PipelineSerializer
    ordering_fields = [
        "id",
        "name",
        "created_at",
        "updated_at",
    ]
    # Don't enable projects filter until we can use the current users
    # membership to filter the projects.
    # filterset_fields = ["projects"]


class PipelineCallbackView(APIView):
    """
    API endpoint that allows pipelines to be executed.
    """

    def post(self, request, *args, **kwargs):
        import pydantic

        from ami.ml.schemas.v2 import PipelineCallbackResponse

        # Parse the request into a PipelineCallbackResponse
        try:
            response = PipelineCallbackResponse(**request.data)
            # if there is a validation error, return a 400 response
        except pydantic.ValidationError as e:
            return Response(e.errors(), status=status.HTTP_400_BAD_REQUEST)
        else:
            # Ensure request ID is valid and the token is correct
            try:
                token = request.headers["Authorization"]
            except KeyError:
                # return unauthenticated
                return Response("Missing authorization header", status=status.HTTP_401_UNAUTHORIZED)

            try:
                pipeline_request = PipelineAsyncRequestRecord(pk=response.pipelineRequestId, token=token)
            except PipelineAsyncRequestRecord.DoesNotExist:
                return Response("Invalid pipeline request ID", status=status.HTTP_400_BAD_REQUEST)
            else:
                pipeline_response = PipelineCallbackResponse(**request.data)
                pipeline_request.response_data = pipeline_response
                pipeline_request.status = PipelineAsyncRequestStatus.COMPLETED
                pipeline_request.save()
                # @TODO Send signal to process the pipeline results

            logger.info(f"Received pipeline results callback: {response}")
            # Format and print the response to the console
            print(response.model_dump_json(indent=2))
            return Response(status=status.HTTP_200_OK)
