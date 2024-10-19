import csv
import json
import logging
from typing import Type

from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class BaseExportSerializer(serializers.Serializer):
    """
    Base serializer for exporting data in various formats, from multiple models.
    """

    pass


class BaseExportView(APIView):
    """
    Read-only API view for exporting data in various formats, from multiple models.
    """

    pass


def get_data_in_batches(QuerySet: models.QuerySet, Serializer: Type[serializers.Serializer], batch_size=1000):
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
            serializer = Serializer(item)
            item_data = serializer.data
            batch.append(item_data)
            logger.info(item_data)

            if len(batch) >= batch_size:
                logger.info(f"Yielding batch {i}")
                yield batch
                batch = []
        except Exception as e:
            logger.warning(f"Error processing item {i}: {str(e)}")
            raise
    if batch:
        yield batch


def write_export(report_name, Serializer: Type[serializers.Serializer], QuerySet: models.QuerySet, format="csv"):
    timestamp = timezone.now().strftime("%Y%m%d-%H%M%S")
    file_name = f"{slugify(report_name)}-{timestamp}.{format}"
    # file_path = f"exports/{file_name}"
    file_path = file_name

    try:
        with default_storage.open(file_path, "w") as file:
            if format == "csv":
                writer = csv.writer(file)
                writer.writerow(Serializer().fields.keys())  # Write header
                for batch in get_data_in_batches(Serializer=Serializer, QuerySet=QuerySet):
                    for item in batch:
                        print(item)
                        writer.writerow(item.values())
            else:  # JSON
                file.write("[")
                first = True
                for batch in get_data_in_batches(Serializer=Serializer, QuerySet=QuerySet):
                    for item in batch:
                        if not first:
                            file.write(",")
                        json.dump(item, file)
                        first = False
                file.write("]")

        # Cache the file path
        cache.set(f"export_{report_name}_{format}", file_path, 3600)  # Cache for 1 hour

        logger.info(f"Export generated successfully: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error generating export: {str(e)}")
        raise
