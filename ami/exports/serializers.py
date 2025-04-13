from django.template.defaultfilters import filesizeformat
from rest_framework import serializers

from ami.base.serializers import DefaultSerializer
from ami.exports.registry import ExportRegistry
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
    file_size_display = serializers.SerializerMethodField()

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
            "file_size_display",
            "created_at",
            "updated_at",
        ]

    def validate_format(self, value):
        supported_formats = ExportRegistry.get_supported_formats()
        if value not in supported_formats:
            raise serializers.ValidationError(f"Invalid format. Supported formats are: {supported_formats}")
        return value

    def get_file_url(self, obj):
        return obj.get_absolute_url(request=self.context.get("request"))

    def get_file_size_display(self, obj):
        """
        Converts file size from bytes to a more readable format.
        """
        if not obj.file_size:
            return None
        return filesizeformat(obj.file_size)
