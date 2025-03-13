"""
Management command that runs the export_by_capture function in exports.py and reports the progress as it processes and
writes batches.
"""

import logging

from django.core.management.base import BaseCommand, CommandParser

from ami.exports import all_sessions
from ami.exports.base import write_export

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Export data by capture"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--project-id",
            type=int,
            required=True,
            help="Project ID to export data from",
        )

    def handle(self, *args, **options):
        # for i, batch in enumerate(by_capture.get_data_in_batches())
        #     # print(f"Processing batch {batch}")
        #     print(f"Processing batch {i}")
        project_id: int = options["project_id"]

        fname = write_export(
            "sessions",
            Serializer=all_sessions.SessionsTabularSerializer,
            QuerySet=all_sessions.get_queryset().filter(project=project_id),
        )
        # get full path to the file
        print(f"Exported to {fname}")

        logger.info("Export by capture completed")
        self.stdout.write(self.style.SUCCESS("Export by capture completed"))
