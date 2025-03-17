from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from ami.base.views import ProjectMixin
from ami.exports.registry import ExportRegistry
from ami.jobs.models import DataExport
from ami.jobs.serializers import DataExportSerializer


class ExportViewSet(ModelViewSet, ProjectMixin):
    """
    API endpoint for exporting occurrences.
    """

    queryset = DataExport.objects.all()
    serializer_class = DataExportSerializer

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

        # Get export format and project from request params
        format_type = request.data.get("format")

        # Validate format using the ExportsRegistry
        if format_type not in ExportRegistry.get_supported_formats():
            return Response(
                {"error": f"Invalid format. Supported formats : {ExportRegistry.get_supported_formats()}"}, status=400
            )
        # Extract filters from request
        filters = request.query_params.dict()

        project = self.get_active_project()

        if not project:
            return Response({"error": "Project ID not provided or invalid"}, status=400)

        # Create a new DataExport entry
        data_export = DataExport.objects.create(
            user=request.user,
            format=format_type,
            filters=filters,
            project=project,
        )
        # Start export job
        data_export.start_job()

        serializer = self.get_serializer(data_export)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
