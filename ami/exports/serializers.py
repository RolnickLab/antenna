from rest_framework import serializers

from ami.main.models import Occurrence


class DefaultExportSerializer(serializers.ModelSerializer):
    pass


def get_export_serializer():
    from ami.main.api.serializers import OccurrenceSerializer

    class OccurrenceExportSerializer(OccurrenceSerializer):
        detection_images = serializers.SerializerMethodField()

        def get_detection_images(self, obj):
            """Convert the generator field to a list before serialization"""
            if hasattr(obj, "detection_images") and callable(obj.detection_images):
                return list(obj.detection_images())  # Convert generator to list
            return []

        def get_permissions(self, instance_data):
            return instance_data

        def to_representation(self, instance):
            return super().to_representation(instance)

    return OccurrenceExportSerializer


class OccurrenceTabularSerializer(DefaultExportSerializer):
    """Serializer to format occurrences for tabular data export."""

    event_id = serializers.IntegerField(source="event.id", allow_null=True)
    event_name = serializers.CharField(source="event.name", allow_null=True)
    deployment_id = serializers.IntegerField(source="deployment.id", allow_null=True)
    deployment_name = serializers.CharField(source="deployment.name", allow_null=True)
    determination_id = serializers.IntegerField(source="determination.id", allow_null=True)
    determination_name = serializers.CharField(source="determination.name", allow_null=True)
    detections_count = serializers.IntegerField()
    first_appearance_timestamp = serializers.DateTimeField()
    duration = serializers.SerializerMethodField()

    def get_duration(self, obj):
        return obj.duration().total_seconds() if obj.duration() else None

    class Meta:
        model = Occurrence
        fields = [
            "id",
            "event_id",
            "event_name",
            "deployment_id",
            "deployment_name",
            "determination_id",
            "determination_name",
            "determination_score",
            "detections_count",
            "first_appearance_timestamp",
            "duration",
        ]
