from rest_framework import serializers

from ami.base.serializers import DefaultSerializer
from ami.jobs.models import Job
from ami.jobs.serializers import JobListSerializer
from ami.main.api.serializers import UserNestedSerializer
from ami.main.models import Project

from .models import DataExport


class DataExportJobNestedSerializer(JobListSerializer):
    """
    Job Nested serializer for DataExport.
    """

    class Meta:
        model = Job
        fields = [
            "id",
            "name",
            "project",
            "progress",
            "result",
        ]


class DataExportSerializer(DefaultSerializer):
    """
    Serializer for DataExport
    """

    job = DataExportJobNestedSerializer(read_only=True)  # Nested job serializer
    user = UserNestedSerializer(read_only=True)
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), write_only=True)
    file_url = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()

    class Meta:
        model = DataExport
        fields = [
            "id",
            "user",
            "project",
            "format",
            "filters",
            "filters_display",
            "job",
            "file_url",
            "record_count",
            "file_size",
            "created_at",
            "updated_at",
        ]

    def get_file_url(self, obj):
        return obj.get_absolute_url(request=self.context.get("request"))

    def get_file_size(self, obj):
        """
        Converts file size from bytes to a more readable format.
        """
        if not obj.file_size:
            return None
        size_in_bytes = obj.file_size
        if size_in_bytes < 1024:
            return f"{size_in_bytes} B"
        elif size_in_bytes < 1024 * 1024:
            return f"{size_in_bytes / 1024:.2f} KB"
        elif size_in_bytes < 1024 * 1024 * 1024:
            return f"{size_in_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_in_bytes / (1024 * 1024 * 1024):.2f} GB"
