"""
Management command that runs the export_by_capture function in exports.py and reports the progress as it processes and
writes batches.
"""

import logging
import typing

from django.core.management.base import BaseCommand
from django.db import models

from ami.exports import by_capture
from ami.exports.base import write_export

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Export data by capture"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--project-id",
            type=int,
            required=True,
            help="Project ID to export data from",
        )
        parser.add_argument(
            "--collection-ids",
            type=int,
            nargs="+",
            required=False,
            default=[],
            help="Collection IDs to export data from (space-separated list)",
        )

    def handle(self, *args, **options) -> None:
        project_id: int = options["project_id"]
        collection_ids: list[int] = options["collection_ids"]

        qs = by_capture.get_queryset().filter(occurrence__project=project_id)
        if collection_ids:
            qs = qs.filter(source_image__collections__in=collection_ids)

        fname = write_export(
            "detections_by_determination_and_capture",
            Serializer=by_capture.DetectionsByDeterminationAndCaptureTabularSerializer,
            QuerySet=typing.cast(models.QuerySet, qs),
        )
        # get full path to the file
        print(f"Exported to {fname}")

        logger.info("Export by capture completed")
        self.stdout.write(self.style.SUCCESS("Export by capture completed"))
