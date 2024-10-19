# Views, serializers and queries for the by_capture export type

"""
This export should contain the following fields:

- Capture ID
- Date Observed
- Time Observed
- Latitude
- Longitude
- Taxon ID (include not-moth)
- Count (count of this taxon in one image)
- Taxon scientific name
- Taxon rank
- Taxon specific epithet
- Taxon genus
- Taxon family
- Softmax score
- Num detections (in same capture)
- Station Name
- Session ID
- Session Start Date
- Session duration
- Device ID
- Detection algorithm ID
- Moth/Not moth classifier algorithm ID
- Species Classification Algorithm ID
- Verification user IDs
- Verified
- Verified on
"""

import logging
import typing

from django.contrib.postgres.aggregates import ArrayAgg
from django.db import models
from rest_framework import serializers

from ami.main.models import Detection, Taxon, TaxonRank

logger = logging.getLogger(__name__)


class DetectionsByDeterminationAndCaptureTabularSerializer(serializers.Serializer):
    """
    Specify the field names, order of fields, and the format of each field value for the export.
    """

    capture_id = serializers.IntegerField(source="source_image_id")
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    datetime_observed = serializers.DateTimeField()
    # date_observed = serializers.DateField()
    # time_observed = serializers.TimeField()
    session_id = serializers.IntegerField()
    session_start_datetime = serializers.DateTimeField()
    session_end_datetime = serializers.DateTimeField()
    session_duration = serializers.DurationField()
    # date_observed = serializers.DateField(# Views, serializers and queries for the by_capture export type
    taxon_id = serializers.IntegerField()
    taxon_name = serializers.CharField()
    taxon_rank = serializers.CharField()
    taxon_count = serializers.IntegerField()
    determination_score_max = serializers.FloatField()
    detection_ids = serializers.CharField()
    occurrence_ids = serializers.CharField()
    station_name = serializers.CharField()
    station_id = serializers.IntegerField()
    device_id = serializers.IntegerField()
    device_name = serializers.CharField()

    def to_representation(self, instance: typing.Any) -> dict[str, typing.Any]:
        data = super().to_representation(instance)
        taxon: Taxon = Taxon.objects.get(id=data["taxon_id"])

        for taxon_rank in taxon.parents_json:
            field_name = f"taxon_{taxon_rank.rank.name.lower()}"
            data[field_name] = taxon_rank.name

        return data

    def get_fields(self):
        fields = super().get_fields()
        for rank in TaxonRank:
            field_name = f"taxon_{rank.name.lower()}"
            fields[field_name] = serializers.CharField(required=False)
        return fields


def get_queryset():
    return (
        Detection.objects.all()
        .select_related(
            "occurrence",
            "occurrence__determination",
            "source_image",
        )
        .values(
            "source_image_id",
            "occurrence__determination_id",
        )
        .annotate(
            # occurrence_id=models.F("occurrence_id"),
            capture_id=models.F("source_image_id"),
            datetime_observed=models.F("source_image__timestamp"),
            # date_observed=models.F("source_image__timestamp__date"),
            # time_observed=models.F("source_image__timestamp__time"),
            latitude=models.F("source_image__deployment__latitude"),
            longitude=models.F("source_image__deployment__longitude"),
            session_id=models.F("source_image__event_id"),
            session_start_datetime=models.F("source_image__event__start"),
            session_end_datetime=models.F("source_image__event__end"),
            # Calculate session duration
            session_duration=models.F("source_image__event__end") - models.F("source_image__event__start"),
            station_name=models.F("source_image__deployment__name"),
            station_id=models.F("source_image__deployment_id"),
            taxon_id=models.F("occurrence__determination_id"),
            taxon_name=models.F("occurrence__determination__name"),
            taxon_rank=models.F("occurrence__determination__rank"),
            determination_score_max=models.Max("occurrence__determination_score"),
            taxon_count=models.Count("id"),
            detection_ids=ArrayAgg("id"),
            occurrence_ids=ArrayAgg("occurrence_id"),
            device_id=models.F("source_image__deployment__device_id"),
            device_name=models.F("source_image__deployment__device__name"),
            # classification_algorithm_id=models.F("occurrence__determination__classification_algorithm_id"),
            # taxon_specific_epithet=models.F("occurrence__determination__specific_epithet"),
            # taxon_genus=models.F("occurrence__determination__genus"),
            # taxon_family=F("determination__family"),
            # num_detections=Count("occurrence__detections"),
            # verification_user_ids=F("occurrence__source_image__collection__session__device__verification_users"),
        )
        # Group the detections by capture and add a count of detections in each capture
        .order_by("source_image_id", "-taxon_count", "-determination_score_max")
    )
