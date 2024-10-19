import logging
import typing

from django.db import models
from django.db.models.functions import TruncDate, TruncTime
from rest_framework import serializers

from ami.main.models import Detection, Taxon, TaxonRank

logger = logging.getLogger(__name__)


class DetectionsTabularSerializer(serializers.Serializer):
    detection_id = serializers.IntegerField(source="id")
    occurrence_id = serializers.IntegerField()
    capture_id = serializers.IntegerField(source="source_image_id")
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    datetime_observed = serializers.DateTimeField()
    date_observed = serializers.DateField()
    time_observed = serializers.TimeField()
    session_id = serializers.IntegerField()
    session_start_datetime = serializers.DateTimeField()
    session_start_date = serializers.DateField()
    session_start_time = serializers.TimeField()
    session_end_datetime = serializers.DateTimeField()
    session_end_date = serializers.DateField()
    session_end_time = serializers.TimeField()
    session_duration = serializers.DurationField()
    taxon_id = serializers.IntegerField()
    taxon_name = serializers.CharField()
    taxon_rank = serializers.CharField()
    determination_score = serializers.FloatField()
    station_name = serializers.CharField()
    station_id = serializers.IntegerField()
    device_id = serializers.IntegerField()
    device_name = serializers.CharField()

    def to_representation(self, instance: typing.Any) -> dict[str, typing.Any]:
        data = super().to_representation(instance)
        taxon: Taxon = instance.occurrence.determination

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
        .annotate(
            capture_id=models.F("source_image_id"),
            datetime_observed=models.F("source_image__timestamp"),
            date_observed=TruncDate("source_image__timestamp"),
            time_observed=TruncTime("source_image__timestamp"),
            latitude=models.F("source_image__deployment__latitude"),
            longitude=models.F("source_image__deployment__longitude"),
            session_id=models.F("source_image__event_id"),
            session_start_datetime=models.F("source_image__event__start"),
            session_start_date=TruncDate("source_image__event__start"),
            session_start_time=TruncTime("source_image__event__start"),
            session_end_datetime=models.F("source_image__event__end"),
            session_end_date=TruncDate("source_image__event__end"),
            session_end_time=TruncTime("source_image__event__end"),
            session_duration=models.F("source_image__event__end") - models.F("source_image__event__start"),
            station_name=models.F("source_image__deployment__name"),
            station_id=models.F("source_image__deployment_id"),
            taxon_id=models.F("occurrence__determination_id"),
            taxon_name=models.F("occurrence__determination__name"),
            taxon_rank=models.F("occurrence__determination__rank"),
            determination_score=models.F("occurrence__determination_score"),
            taxon_count=models.Count("id"),
            device_id=models.F("source_image__deployment__device_id"),
            device_name=models.F("source_image__deployment__device__name"),
        )
        .order_by("source_image_id", "-determination_score")
    )
