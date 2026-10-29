from django.core.management.base import BaseCommand

from ami.main.models import Occurrence
from ami.main.models_future.occurrence_size import update_occurrence_sizes_in_queryset


class Command(BaseCommand):
    help = (
        "Calculate the stored size of occurrences from their detection boxes. "
        "Run once after deploying the size fields, and again after bulk changes to detections."
    )

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, action="append", help="Only this project (repeatable)")
        parser.add_argument("--deployment", type=int, action="append", help="Only this deployment (repeatable)")

    def handle(self, *args, **options):
        occurrences = Occurrence.objects.all()
        if options["project"]:
            occurrences = occurrences.filter(project_id__in=options["project"])
        if options["deployment"]:
            occurrences = occurrences.filter(deployment_id__in=options["deployment"])
        updated = update_occurrence_sizes_in_queryset(occurrences)
        self.stdout.write(self.style.SUCCESS(f"Updated the size of {updated} occurrences"))
