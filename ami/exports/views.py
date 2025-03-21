from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from ami.base.views import ProjectMixin
from ami.exports.registry import ExportRegistry
from ami.exports.serializers import DataExportSerializer
from ami.jobs.models import DataExportJob, Job, SourceImageCollection

from .models import DataExport


class ExportViewSet(ModelViewSet, ProjectMixin):
    """
    API endpoint for exporting occurrences.
    """

    queryset = DataExport.objects.all()
    serializer_class = DataExportSerializer
    ordering_fields = ["id", "format", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = self.queryset.select_related("job")
        project = self.get_active_project()
        if project:
            queryset = queryset.filter(project=project)
        return queryset

    def create(self, request, *args, **kwargs):
        """
        Create a new DataExport entry and trigger the export job.
        """

        # Get export format from request body
        format_type = request.data.get("format")
        filters = request.data.get("filters", {})
        collection_id = filters.get("collection")
        # Validate format using the ExportsRegistry
        if format_type not in ExportRegistry.get_supported_formats():
            return Response(
                {"error": f"Invalid format. Supported formats : {ExportRegistry.get_supported_formats()}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = self.get_active_project()

        if not project:
            return Response({"error": "Project ID not provided or invalid"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            collection = SourceImageCollection.objects.get(pk=collection_id)
        except SourceImageCollection.DoesNotExist:
            return Response(
                {"error": "Collection ID not provided or does not exist."}, status=status.HTTP_400_BAD_REQUEST
            )
        if collection.project != project:
            return Response(
                {"error": "Collection does not belong to the selected project."}, status=status.HTTP_400_BAD_REQUEST
            )
        # Create a new DataExport entry
        data_export = DataExport.objects.create(
            user=request.user,
            format=format_type,
            filters=filters,
            project=project,
        )

        # Start export job
        job = Job.objects.create(
            name=f"Export occurrences for collection {collection.pk}",
            project=project,
            job_type_key=DataExportJob.key,
            data_export=data_export,
            params={"filters": filters, "format": format_type},
        )
        job.enqueue()

        serializer = self.get_serializer(data_export)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
