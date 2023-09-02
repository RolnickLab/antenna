from rest_framework import serializers

from ami.main.api.serializers import add_format_to_url, reverse_with_params
from ami.main.models import Detection, Occurrence, SourceImage


class LabelStudioBatchSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = SourceImage
        fields = ["url"]

    def get_url(self, obj):
        # return f"https://example.com/label-studio/captures/{obj.pk}/"
        url = reverse_with_params(
            "api:labelstudio-captures-detail",
            request=self.context.get("request"),
            args=[obj.pk],
        )
        url = add_format_to_url(url, "json")
        return url


class LabelStudioSourceImageSerializer(serializers.ModelSerializer):
    """
    Serialize source images for manual annotation of detected objects in Label Studio.

    Manually specifies the json output to match the Label Studio task format.
    https://labelstud.io/guide/tasks.html#Example-JSON-format
    """

    data = serializers.SerializerMethodField()
    annotations = serializers.SerializerMethodField()
    predictions = serializers.SerializerMethodField()

    class Meta:
        model = SourceImage
        fields = ["data", "annotations", "predictions"]

    def get_data(self, obj):
        deployment_name = obj.deployment.name if obj.deployment else ""
        project_name = obj.deployment.project.name if obj.deployment and obj.deployment.project else ""
        # public_url = obj.deployment.data_source.public_url(obj.path)
        return {
            "image": obj.public_url(),
            "ami_id": obj.pk,
            "timestamp": obj.timestamp,
            "deployment": (obj.deployment.name if obj.deployment else None),
            "deployment_id": (obj.deployment.pk if obj.deployment else None),
            "project": (obj.deployment.project.name if obj.deployment and obj.deployment.project else None),
            "project_id": (obj.deployment.project.pk if obj.deployment and obj.deployment.project else None),
            "location": f"{project_name} / {deployment_name}",
        }

    def get_annotations(self, obj):
        # @TODO implement if necessary, make optional by URL param
        return []

    def get_predictions(self, obj):
        # @TODO implement if necessary, make optional by URL param
        return []


class LabelStudioDetectionSerializer(serializers.ModelSerializer):
    """
    Serialize detections for manual annotation of objects of interest in Label Studio.

    Manually specifies the json output to match the Label Studio task format.
    https://labelstud.io/guide/tasks.html
    """

    data = serializers.SerializerMethodField()
    annotations = serializers.SerializerMethodField()
    predictions = serializers.SerializerMethodField()

    class Meta:
        model = Detection
        fields = ["data", "annotations", "predictions"]

    def get_data(self, obj):
        # public_url = obj.deployment.data_source.public_url(obj.path)

        return {
            "image": obj.public_url(),
            "ami_id": obj.pk,
            "timestamp": obj.timestamp,
            "deployment": (obj.source_image.deployment.name if obj.source_image.deployment else None),
            "deployment_id": (obj.source_image.deployment.pk if obj.source_image.deployment else None),
            "occurrence_id": (obj.occurrence.pk if obj.occurrence else None),
            "project": (
                obj.source_image.deployment.project.name
                if obj.source_image.deployment and obj.source_image.deployment.project
                else None
            ),
            "project_id": (
                obj.source_image.deployment.project.pk
                if obj.source_image.deployment and obj.source_image.deployment.project
                else None
            ),
            "source_image": obj.source_image.url(),
            "source_image_id": obj.source_image.pk,
        }

    def get_annotations(self, obj):
        return [
            # {
            #     "result": [
            #         {
            #             "type": "choices",
            #             "value": {
            #                 "choices": [
            #                     "Moth",  # these become the selected choice!
            #                     "Non-Moth",
            #                 ]
            #             },
            #             "choice": "single",
            #             "to_name": "image",
            #             "from_name": "choice",
            #         }
            #     ],
            # }
        ]

    def get_predictions(self, obj):
        # @TODO implement if necessary, make optional by URL param
        return []


class LabelStudioOccurrenceSerializer(serializers.ModelSerializer):
    """
    Serialize occurrences for manual annotation of objects of interest in Label Studio.

    Manually specifies the json output to match the Label Studio task format.
    https://labelstud.io/guide/tasks.html
    """

    data = serializers.SerializerMethodField()
    annotations = serializers.SerializerMethodField()
    predictions = serializers.SerializerMethodField()

    class Meta:
        model = Occurrence
        fields = ["data", "annotations", "predictions"]

    def get_data(self, obj):
        best_detection: Detection = obj.best_detection()
        first_appearance: SourceImage = obj.first_appearance()
        deployment_name = obj.deployment.name if obj.deployment else ""
        project_name = obj.deployment.project.name if obj.deployment and obj.deployment.project else ""
        return {
            "image": best_detection.url(),
            "ami_id": obj.pk,
            "url": obj.url(),
            "context_url": obj.context_url(),
            "deployment": (obj.deployment.name if obj.deployment else None),
            "deployment_id": (obj.deployment.pk if obj.deployment else None),
            "project": (obj.deployment.project.name if obj.deployment and obj.deployment.project else None),
            "project_id": (obj.deployment.project.pk if obj.deployment and obj.deployment.project else None),
            "event": (obj.event.day() if obj.event else None),
            "source_image": best_detection.url(),
            "source_image_id": best_detection.pk,
            "details_link": f"<a href='{obj.url()}' target='_blank'>View Details</a>",
            "context_link": f"<a href='{obj.context_url()}' target='_blank'>View Context</a>",
            "details_url": obj.url(),
            "table": {
                "Location": f"{project_name} / {deployment_name}",
                "Date": (obj.event.day().strftime("%B %m, %Y") if obj.event else None),
                "First Appearance": first_appearance.timestamp.strftime("%I:%M %p")
                if first_appearance.timestamp
                else None,
            },
        }

    def get_annotations(self, obj):
        return []

    def get_predictions(self, obj):
        # @TODO implement if necessary, make optional by URL param
        return []
