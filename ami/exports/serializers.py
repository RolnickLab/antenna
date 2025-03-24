from rest_framework import serializers

from ami.base.serializers import DefaultSerializer
from ami.jobs.models import Job
from ami.jobs.serializers import JobListSerializer
from ami.main.api.serializers import UserNestedSerializer
from ami.main.models import Project, SourceImageCollection

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
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), write_only=True)
    collection = serializers.SerializerMethodField()

    class Meta:
        model = DataExport
        fields = [
            "id",
            "user",
            "project",
            "format",
            "filters",
            "collection",
            "job",
            "file_url",
            "created_at",
            "updated_at",
        ]

    def get_collection(self, obj):
        """
        Returns the SourceImageCollection name if 'collection' is in filters.
        """
        collection_id = obj.filters.get("collection") if obj.filters else None
        if collection_id:
            try:
                return SourceImageCollection.objects.get(id=collection_id).name
            except SourceImageCollection.DoesNotExist:
                return None
        return None
