import csv
import logging
import typing

from django.core.files.storage import default_storage
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework.views import APIView
from tqdm import tqdm

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


def get_data_in_batches(
    QuerySet: models.QuerySet,
    Serializer: type[serializers.Serializer],
    batch_size: int = 1000,
) -> typing.Iterator[list[dict]]:
    items = QuerySet.iterator(chunk_size=batch_size)
    batch = []
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

            if len(batch) >= batch_size:
                yield batch
                batch = []
        except Exception as e:
            logger.warning(f"Error processing item {i}: {str(e)}")
            raise
    if batch:
        yield batch


def write_export(
    report_name: str,
    Serializer: type[serializers.Serializer],
    QuerySet: models.QuerySet,
) -> str:
    timestamp = timezone.now().strftime("%Y%m%d-%H%M%S")
    file_name = f"{slugify(report_name)}-{timestamp}.csv"
    file_path = file_name

    try:
        with default_storage.open(file_path, "w") as file:
            writer = csv.writer(file)
            writer.writerow(Serializer().fields.keys())  # Write header

            # Calculate total items for progress bar
            total_items = QuerySet.count()

            with tqdm(total=total_items, desc="Exporting data", unit="items") as pbar:
                for batch in get_data_in_batches(Serializer=Serializer, QuerySet=QuerySet):
                    for item in batch:
                        writer.writerow(item.values())
                        pbar.update(1)

        logger.info(f"CSV export generated successfully: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error generating CSV export: {str(e)}")
        raise
