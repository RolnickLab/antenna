"""
Management command that runs the export_by_capture function in exports.py and reports the progress as it processes and
writes batches.
"""

import logging

from django.core.management.base import BaseCommand

from ami.exports import all_captures
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

    def handle(self, *args, **options):
        # for i, batch in enumerate(by_capture.get_data_in_batches())
        #     # print(f"Processing batch {batch}")
        #     print(f"Processing batch {i}")
        project_id: int = options["project_id"]
        collection_ids: list[int] = options["collection_ids"]

        qs = all_captures.get_queryset().filter(project=project_id)
        if collection_ids:
            qs = qs.filter(collections__in=collection_ids)

        fname = write_export(
            "captures",
            Serializer=all_captures.CapturesTabularSerializer,
            QuerySet=qs,
        )
        # get full path to the file
        print(f"Exported to {fname}")

        logger.info("Export by capture completed")
        self.stdout.write(self.style.SUCCESS("Export by capture completed"))
