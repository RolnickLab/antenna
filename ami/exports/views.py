from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from ami.base.views import ProjectMixin
from ami.exports.registry import ExportRegistry
from ami.jobs.models import DataExport, DataExportJob, Job, JobState
from ami.jobs.serializers import DataExportSerializer


class ExportViewSet(ModelViewSet, ProjectMixin):
    """
    API endpoint for exporting occurrences.
    """

    queryset = DataExport.objects.all()
    serializer_class = DataExportSerializer  # Make sure to create a serializer for DataExport

    def create(self, request, *args, **kwargs):
        """
        Create a new DataExport entry and trigger the export job.
        """

        # Get export format and project from request params
        format_type = request.data.get("format").lower()

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

        # Create a Job for export
        job = Job.objects.create(
            name=f"{project} Export Occurrences ({format_type.upper()})",
            project=project,
            job_type_key=DataExportJob.key,
            params={"filters": filters, "format": format_type},  # Pass export params
        )

        # Create a new DataExport entry linked to the job
        data_export = DataExport.objects.create(
            user=request.user,
            job=job,
            format=format_type,
            status=JobState.PENDING,
        )

        # Enqueue the job
        job.enqueue()

        return Response(
            {"export_id": data_export.pk, "job_id": job.pk, "format": format_type, "project_id": project.pk},
            status=201,
        )

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a DataExport record and return job status.
        """
        data_export = get_object_or_404(DataExport, pk=kwargs["pk"])
        job = data_export.job  # Get associated job

        response_data = {
            "export_id": data_export.pk,
            "job_id": job.pk,
            "status": job.status,
            "progress": job.progress.summary.progress,
            "format": data_export.format,
            "created_at": job.scheduled_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
        }

        # If the job is complete, include the file URL
        if job.status == JobState.SUCCESS and job.result:
            response_data["file_url"] = job.result.get("file_url", None)
            data_export.file_url = response_data["file_url"]
            data_export.status = JobState.SUCCESS
            data_export.save()

        return Response(response_data)

    def list(self, request, *args, **kwargs):
        """
        Retrieve all data exports and allow filtering by project_id.
        """
        project = self.get_active_project()

        if project:
            exports = self.queryset.filter(job__project=project)
        else:
            exports = self.queryset

        serializer = self.get_serializer(exports, many=True)
        return Response(serializer.data)
