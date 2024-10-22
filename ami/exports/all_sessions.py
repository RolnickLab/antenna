import logging
import typing

from django.db import models
from django.db.models.functions import TruncDate, TruncTime
from rest_framework import serializers

from ami.main.models import Event

logger = logging.getLogger(__name__)


class SessionsTabularSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(source="id")
    session_start_datetime = serializers.DateTimeField()
    session_start_date = serializers.DateField()
    session_start_time = serializers.TimeField()
    session_end_datetime = serializers.DateTimeField()
    session_end_date = serializers.DateField()
    session_end_time = serializers.TimeField()
    session_duration = serializers.DurationField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    station_name = serializers.CharField()
    station_id = serializers.IntegerField()
    device_id = serializers.IntegerField()
    device_name = serializers.CharField()
    captures_count = serializers.IntegerField(source="captures_count_fresh")
    detections_count = serializers.IntegerField(source="detections_count_fresh")
    occurrences_count = serializers.IntegerField()
    taxa_count = serializers.IntegerField()


def get_queryset():
    return (
        Event.objects.all()
        .annotate(
            session_id=models.F("id"),
            session_start_datetime=models.F("start"),
            session_start_date=TruncDate("start"),
            session_start_time=TruncTime("start"),
            session_end_datetime=models.F("end"),
            session_end_date=TruncDate("end"),
            session_end_time=TruncTime("end"),
            session_duration=models.F("end") - models.F("start"),
            latitude=models.F("deployment__latitude"),
            longitude=models.F("deployment__longitude"),
            station_name=models.F("deployment__name"),
            station_id=models.F("deployment_id"),
            device_id=models.F("deployment__device_id"),
            device_name=models.F("deployment__device__name"),
            captures_count_fresh=models.Count("captures", distinct=True),
            detections_count_fresh=models.Count("captures__detections", distinct=True),
            occurrences_count_fresh=models.Count("captures__detections__occurrence", distinct=True),
            taxa_count=models.Count("captures__detections__occurrence__determination", distinct=True),
        )
        .order_by("session_start_datetime", "station_id")
    )
