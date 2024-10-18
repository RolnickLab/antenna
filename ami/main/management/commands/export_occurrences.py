import json
import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.test.client import RequestFactory
from tqdm import tqdm

from ami.main.api.serializers import OccurrenceSerializer
from ami.main.models import Deployment, Occurrence, Project

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class OccurrenceExportSerializer(OccurrenceSerializer):
    class Meta(OccurrenceSerializer.Meta):
        extra_kwargs = {
            "url": {"view_name": "api:occurrence-detail"},
        }

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        for field in self.fields:
            try:
                logger.debug(f"Processing field: {field}")
                representation[field] = self.fields[field].to_representation(getattr(instance, field))
            except Exception as e:
                logger.error(f"Error processing field {field}: {e}")
                raise e
        return representation


class Command(BaseCommand):
    help = "Export Occurrence model instances to JSON"

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, help="Filter by project ID")
        parser.add_argument("--deployment", type=int, help="Filter by deployment ID")
        parser.add_argument("--start-date", type=str, help="Filter by start date (YYYY-MM-DD)")
        parser.add_argument("--end-date", type=str, help="Filter by end date (YYYY-MM-DD)")
        parser.add_argument("--output", type=str, default="occurrences_export.json", help="Output file name")
        parser.add_argument("--limit", type=int, default=10, help="Limit the number of occurrences to export")
        parser.add_argument(
            "--base-url", type=str, default="http://example.com", help="Base URL for hyperlinked fields"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        queryset = Occurrence.objects.all()

        if options["project"]:
            try:
                project = Project.objects.get(pk=options["project"])
                queryset = queryset.filter(project=project)
            except Project.DoesNotExist:
                raise CommandError(f"Project with ID {options['project']} does not exist")

        if options["deployment"]:
            try:
                deployment = Deployment.objects.get(pk=options["deployment"])
                queryset = queryset.filter(deployment=deployment)
            except Deployment.DoesNotExist:
                raise CommandError(f"Deployment with ID {options['deployment']} does not exist")

        date_filter = Q()
        if options["start_date"]:
            date_filter &= Q(event__start__gte=options["start_date"])
        if options["end_date"]:
            date_filter &= Q(event__start__lte=options["end_date"])
        queryset = queryset.filter(date_filter)

        limit = options["limit"]
        queryset = queryset[:limit]
        total_occurrences = queryset.count()
        self.stdout.write(f"Exporting up to {limit} occurrences...")

        serialized_data = []

        # Create a fake request for the serializer context
        factory = RequestFactory()
        fake_request = factory.get("/")
        fake_request.META["HTTP_HOST"] = options["base_url"]

        for occurrence in tqdm(queryset, total=total_occurrences, desc="Exporting occurrences"):
            serializer = OccurrenceExportSerializer(occurrence, context={"request": fake_request})
            serialized_data.append(serializer.data)

        with open(options["output"], "w") as f:
            json.dump(serialized_data, f, indent=2)

        self.stdout.write(
            self.style.SUCCESS(f"Successfully exported {total_occurrences} occurrences to {options['output']}")
        )
