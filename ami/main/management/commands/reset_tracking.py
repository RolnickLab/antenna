"""
Undo tracking for one or more sessions, so they can be tracked again from scratch.

Splits every multi-detection occurrence back into one occurrence per detection, clears
the chain links and grouping confirmations, and prints the counts before and after. See
``ami/main/models_future/session_reset.py`` for exactly what changes. Each session is
reset in its own transaction.
"""

import dataclasses
import logging

from django.core.management.base import BaseCommand, CommandError

from ami.main.models import Event
from ami.main.models_future.session_reset import SessionResetRefused, reset_session_tracking

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Split a session's tracked occurrences back into one occurrence per detection."

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, required=True, help="Project the sessions belong to.")
        parser.add_argument(
            "--event",
            type=int,
            action="append",
            dest="events",
            required=True,
            help="Session (event) ID to reset. Repeat to reset several.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Report what would change and write nothing.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reset even when occurrences in the session carry human identifications.",
        )

    def handle(self, *args, **options):
        project_id: int = options["project"]
        event_ids: list[int] = options["events"]
        events = {event.pk: event for event in Event.objects.filter(project_id=project_id, pk__in=event_ids)}
        missing = [pk for pk in event_ids if pk not in events]
        if missing:
            raise CommandError(f"Session(s) {missing} not found in project {project_id}")

        refused = []
        for pk in event_ids:
            try:
                result = reset_session_tracking(events[pk], force=options["force"], dry_run=options["dry_run"])
            except SessionResetRefused as error:
                self.stderr.write(str(error))
                refused.append(pk)
                continue
            summary = {k: v for k, v in dataclasses.asdict(result).items() if k not in ("before", "after")}
            logger.info(f"reset_tracking: {summary}")
            self.stdout.write(f"Session {pk}{' (dry run)' if result.dry_run else ''}: {summary}")
            self.stdout.write(f"  before: {dataclasses.asdict(result.before)}")
            if result.after is not None:
                self.stdout.write(f"  after:  {dataclasses.asdict(result.after)}")
        if refused:
            raise CommandError(f"Refused to reset session(s) {refused}; see above.")
