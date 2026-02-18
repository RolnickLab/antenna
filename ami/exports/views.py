from rest_framework import status
from rest_framework.response import Response

from ami.base.permissions import ObjectPermission
from ami.base.views import ProjectMixin
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
    permission_classes = [ObjectPermission]
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

        # Check optional collection filter
        collection = None
        collection_id = filters.get("collection_id")
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

        # Create unsaved DataExport instance
        data_export = DataExport(
            user=request.user,
            format=format_type,
            filters=filters,
            project=project,
        )

        # Check permissions on the unsaved instance
        self.check_object_permissions(request, data_export)

        # Save the instance after permission check passes
        data_export.save()
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
