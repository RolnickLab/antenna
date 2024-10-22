"""
Management command that runs the export_by_capture function in exports.py and reports the progress as it processes and
writes batches.
"""

import logging

from django.core.management.base import BaseCommand

from ami.exports import all_sessions
from ami.exports.base import write_export

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Export data by capture"

    def handle(self, *args, **options):
        # for i, batch in enumerate(by_capture.get_data_in_batches())
        #     # print(f"Processing batch {batch}")
        #     print(f"Processing batch {i}")

        fname = write_export(
            "sessions",
            Serializer=all_sessions.SessionsTabularSerializer,
            QuerySet=all_sessions.get_queryset().filter(project=85),
        )
        # get full path to the file
        print(f"Exported to {fname}")

        logger.info("Export by capture completed")
        self.stdout.write(self.style.SUCCESS("Export by capture completed"))
