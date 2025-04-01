from rest_framework import status
from rest_framework.response import Response

from ami.base.views import ProjectMixin
from ami.exports.registry import ExportRegistry
from ami.exports.serializers import DataExportSerializer
from ami.jobs.models import DataExportJob, Job, SourceImageCollection
from ami.main.api.views import DefaultViewSet

from .models import DataExport


class ExportViewSet(DefaultViewSet, ProjectMixin):
    """
    API endpoint for exporting occurrences.
    """

    queryset = DataExport.objects.all()
    serializer_class = DataExportSerializer
    ordering_fields = ["id", "format", "file_size", "created_at", "updated_at"]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("job")
        project = self.get_active_project()
        if project:
            queryset = queryset.filter(project=project)
        return queryset

    def create(self, request, *args, **kwargs):
        """
        Create a new DataExport entry and trigger the export job.
        """

        # Use serializer for validation
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        format_type = validated_data["format"]
        filters = validated_data.get("filters", {})
        project = validated_data["project"]

        # Validate format
        if format_type not in ExportRegistry.get_supported_formats():
            return Response(
                {"error": f"Invalid format. Supported formats : {ExportRegistry.get_supported_formats()}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check optional collection filter
        collection = None
        collection_id = filters.get("collection")
        if collection_id:
            try:
                collection = SourceImageCollection.objects.get(pk=collection_id)
            except SourceImageCollection.DoesNotExist:
                return Response(
                    {"error": "Collection does not exist."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if collection.project != project:
                return Response(
                    {"error": "Collection does not belong to the selected project."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Create DataExport object
        data_export = DataExport.objects.create(
            user=request.user,
            format=format_type,
            filters=filters,
            project=project,
        )
        data_export.update_record_count()

        job_name = f"Export occurrences{f' for collection {collection.pk}' if collection else ''}"
        job = Job.objects.create(
            name=job_name,
            project=project,
            job_type_key=DataExportJob.key,
            data_export=data_export,
            source_image_collection=collection,
        )
        job.enqueue()

        return Response(self.get_serializer(data_export).data, status=status.HTTP_201_CREATED)
