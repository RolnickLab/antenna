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

from django.db import models
from rest_framework import serializers

from ami.main.models import Detection

logger = logging.getLogger(__name__)


class DetectionsByDeterminatinonAndCaptureSerializer(serializers.Serializer):
    """
    Specify the field names, order of fields, and the format of each field value for the export.
    """

    capture_id = serializers.IntegerField(source="source_image_id")
    # date_observed = serializers.DateField()
    # time_observed = serializers.TimeField()
    # latitude = serializers.FloatField()
    # longitude = serializers.FloatField()
    # taxon_id = serializers.IntegerField()
    # taxon_scientific_name = serializers.CharField()


def get_queryset():
    return (
        Detection.objects.all()
        .select_related(
            "occurrence",
            "source_image",
        )
        .prefetch_related()
        .values(
            "occurrence_id",
            "source_image_id",
            "source_image__timestamp",
            "source_image__deployment__latitude",
            "source_image__deployment__longitude",
            "occurrence__determination_id",
            "occurrence__determination_score",
        )
        .annotate(
            taxon_scientific_name=models.F("occurrence__determination__display_name"),
            taxon_rank=models.F("occurrence__determination__rank"),
            # taxon_family=F("determination__family"),
            # num_detections=Count("occurrence__detections"),
            # verification_user_ids=F("occurrence__source_image__collection__session__device__verification_users"),
        )
    )


def get_data_in_batches(batch_size=1000):
    QuerySet = get_queryset()
    items = QuerySet.iterator(chunk_size=batch_size)
    batch = []
    logger.info(f"QuerySet: {QuerySet}")
    for i, item in enumerate(items):
        # logger.info(f"Processing item {i}")
        try:
            # item_data = {
            #     "user_id": item.id,
            #     "username": item.username,
            #     "email": item.email,
            #     "total_orders": Order.objects.filter(user=item).count(),
            #     "total_spent": Order.objects.filter(user=item).aggregate(total=Sum("total_amount"))["total"] or 0,
            # }
            item_data = item
            serializer = DetectionsByDeterminatinonAndCaptureSerializer(data=item_data)
            if serializer.is_valid():
                batch.append(serializer.validated_data)
            else:
                logger.warning(f"Invalid data for item {i}: {serializer.errors}")
            logger.info(item_data)

            if len(batch) >= batch_size:
                logger.info(f"Yielding batch {i}")
                yield batch
                batch = []
        except Exception as e:
            logger.warning(f"Error processing item {i}: {str(e)}")
    if batch:
        yield batch
