import logging
import typing

from django.db import models
from django.db.models.functions import TruncDate, TruncTime
from rest_framework import serializers

from ami.main.models import Detection, SourceImage, Taxon, TaxonRank

logger = logging.getLogger(__name__)


class CapturesTabularSerializer(serializers.Serializer):
    capture_id = serializers.IntegerField(source="id")
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
    station_name = serializers.CharField()
    station_id = serializers.IntegerField()
    device_id = serializers.IntegerField()
    device_name = serializers.CharField()
    detections_count = serializers.IntegerField(source="detections_count_fresh")
    occurrences_count = serializers.IntegerField()
    taxa_count = serializers.IntegerField()


def get_queryset():
    return (
        SourceImage.objects.all()
        .annotate(
            datetime_observed=models.F("timestamp"),
            date_observed=TruncDate("timestamp"),
            time_observed=TruncTime("timestamp"),
            latitude=models.F("deployment__latitude"),
            longitude=models.F("deployment__longitude"),
            session_id=models.F("event_id"),
            session_start_datetime=models.F("event__start"),
            session_start_date=TruncDate("event__start"),
            session_start_time=TruncTime("event__start"),
            session_end_datetime=models.F("event__end"),
            session_end_date=TruncDate("event__end"),
            session_end_time=TruncTime("event__end"),
            session_duration=models.F("event__end") - models.F("event__start"),
            station_name=models.F("deployment__name"),
            station_id=models.F("deployment_id"),
            device_id=models.F("deployment__device_id"),
            device_name=models.F("deployment__device__name"),
            detections_count_fresh=models.Count("detections", distinct=True),
            occurrences_count=models.Count("detections__occurrence", distinct=True),
            taxa_count=models.Count("detections__occurrence__determination", distinct=True),
        )
        .order_by("datetime_observed")
    )
