from ami.base.serializers import DefaultSerializer
from ami.jobs.models import Job
from ami.jobs.serializers import JobListSerializer

# from ami.jobs.serializers import JobListSerializer
from ami.main.api.serializers import UserNestedSerializer

from .models import DataExport


class DataExportJobNestedSerializer(JobListSerializer):
    """
    Job Nested serializer for DataExport.
    """

    class Meta:
        model = Job
        fields = ["id", "name", "project", "progress", "result"]


class DataExportSerializer(DefaultSerializer):
    """
    Serializer for DataExport
    """

    job = DataExportJobNestedSerializer(read_only=True)  # Nested job serializer
    user = UserNestedSerializer(read_only=True)

    class Meta:
        model = DataExport
        fields = ["id", "user", "format", "filters", "job", "file_url", "created_at", "updated_at"]
