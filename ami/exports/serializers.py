from django.template.defaultfilters import filesizeformat
from rest_framework import serializers

from ami.base.serializers import DefaultSerializer
from ami.exports.registry import ExportRegistry
from ami.jobs.models import Job
from ami.jobs.serializers import JobListSerializer
from ami.main.api.serializers import UserNestedSerializer
from ami.main.models import OccurrenceSet, Project

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

    def validate(self, attrs):
        """Refuse an occurrence set the export's project cannot use: another project's set."""
        attrs = super().validate(attrs)
        filters = attrs.get("filters") or {}
        if "occurrence_set_id" not in filters:
            return attrs
        field = serializers.IntegerField(min_value=1)
        try:
            occurrence_set_id = field.run_validation(filters["occurrence_set_id"])
        except serializers.ValidationError as e:
            raise serializers.ValidationError({"filters": {"occurrence_set_id": e.detail}})
        project = attrs.get("project") or getattr(self.instance, "project", None)
        if not OccurrenceSet.objects.for_project(project).filter(pk=occurrence_set_id).exists():
            raise serializers.ValidationError(
                {"filters": {"occurrence_set_id": ["Occurrence set does not exist in the selected project."]}}
            )
        attrs["filters"] = {**filters, "occurrence_set_id": occurrence_set_id}
        return attrs

    def get_file_url(self, obj):
        return obj.get_absolute_url(request=self.context.get("request"))

    def get_file_size_display(self, obj):
        """
        Converts file size from bytes to a more readable format.
        """
        if not obj.file_size:
            return None
        return filesizeformat(obj.file_size)
