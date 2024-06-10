import logging

from django.core.management.base import BaseCommand, CommandError  # noqa

from ...models import Event

logger = logging.getLogger(__name__)


def fix_events():
    checked = 0
    fixed = 0
    failed = 0
    for event in Event.objects.all():
        checked += 1

        # Try to repair events that are missing a deployment.
        # This may happen if the deployment was deleted, but the event was not.
        # We don't want to to delete processed data if we can avoid it, so deployment was set to null.
        if event.deployment is None:
            deployment = None
            example_capture = event.captures.filter(deployment__isnull=False).first()
            if example_capture and example_capture.deployment is not None:
                deployment = example_capture.deployment
            else:
                example_occurrence = event.occurrences.filter(deployment__isnull=False).first()
                if example_occurrence and example_occurrence.deployment is not None:
                    deployment = example_occurrence.deployment
            if deployment is not None:
                event.deployment = deployment
                event.save()
                fixed += 1
                msg = (
                    f"Fixed event {event} (project: {event.project}) that was missing deployment, "
                    f"associated: {deployment}"
                )
                logger.info(msg)
            else:
                failed += 1
                msg = (
                    f"Event {event} (project: {event.project}) is missing deployment and cannot be fixed. "
                    "Recommend deleting it."
                )
                logger.warning(msg)

    return checked, fixed, failed


class Command(BaseCommand):
    r"""Audit and fix missing relationships to Events, Occurrences, and other types."""

    help = "Audit and fix missing relationships to Events, Occurrences, and other types"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Do not make any changes")

    def handle(self, *args, **options):
        checked, fixed, failed = fix_events()
        msg = f"Checked {checked} events"
        self.stdout.write(msg)
        if fixed:
            msg = f"Fixed {fixed} of {checked} events"
            self.stdout.write(self.style.SUCCESS(msg))
        if failed:
            msg = f"Could not fix {failed} of {checked} events"
            self.stdout.write(self.style.WARNING(msg))
