from django.core.management.base import BaseCommand, CommandError  # noqa
from rich import print

import ami.reports


class Command(BaseCommand):
    r"""Export summaries of data in various formats."""

    help = "Export summaries of data in various formats"

    def add_arguments(self, parser):
        parser.add_argument(
            "report_method",
        )

    def handle(self, *args, **options):
        report_method = getattr(ami.reports, options["report_method"])
        df = report_method(as_dataframe=True)
        print(df.tail(20))
        fname = f"reports/{options['report_method']}.csv"
        msg = f"Exporting {len(df)} rows to {fname}"
        self.stdout.write(self.style.SUCCESS(msg))
        df.to_csv(fname, index=False)
