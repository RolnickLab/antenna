from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from ami.jobs.models import DataExportJob, Job, JobState
from ami.main.models import Occurrence
from ami.utils.requests import get_active_project


class OccurrenceExportViewSet(ReadOnlyModelViewSet):
    """
    API endpoint for exporting occurrences.
    """

    queryset = Occurrence.objects.all()

    def list(self, request, *args, **kwargs):
        format_type = request.query_params.get("file_format", "json").lower()  # Default to JSON

        # Validate format
        valid_formats = ["csv", "json", "darwin_core"]
        if format_type not in valid_formats:
            return Response({"error": f"Invalid format. Supported formats: {', '.join(valid_formats)}"}, status=400)

        # Validate and retrieve the project
        project = get_active_project(request)
        if not project:
            return Response({"error": "Project ID not provided or invalid"}, status=400)

        # Create a job for export
        job = Job.objects.create(
            name=f"{project} Export Occurrences ({format_type.lower()})",
            project=project,
            job_type_key=DataExportJob.key,
            result={"format": format_type},
        )

        # Enqueue the job
        job.enqueue()

        return Response({"job_id": job.pk, "format": format_type, "project_id": project.pk})

    @action(detail=False, methods=["get"])
    def export_status(self, request):
        """
        Check the status of an export job.
        """
        job_id = request.query_params.get("job_id")
        if not job_id:
            return Response({"error": "job_id is required"}, status=400)

        try:
            job = Job.objects.get(pk=job_id, job_type_key=DataExportJob.key)
        except Job.DoesNotExist:
            return Response({"error": "Invalid or unknown job ID"}, status=404)

        response_data = {
            "job_id": job.pk,
            "status": job.status,
            "progress": job.progress.summary.progress,
            "created_at": job.scheduled_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
        }

        # Check if the job is complete and return the file URL
        if job.status == JobState.SUCCESS and job.result:
            response_data["file_url"] = job.result.get("file_url", None)

        return Response(response_data)
