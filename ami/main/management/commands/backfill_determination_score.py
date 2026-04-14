import logging

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef

from ...models import Identification, Occurrence

logger = logging.getLogger(__name__)


def backfill_human_determination_scores(dry_run: bool = True, project_id: int | None = None) -> str:
    """Set determination_score=None for occurrences determined by a human identification.

    A human-determined occurrence is one with at least one non-withdrawn Identification.
    The ML confidence that previously lived in determination_score is preserved in
    best_machine_prediction_score (available via the with_best_machine_prediction
    queryset annotation).
    """
    has_identification = Identification.objects.filter(
        occurrence=OuterRef("pk"),
        withdrawn=False,
    )
    qs = Occurrence.objects.filter(determination_score__isnull=False).filter(Exists(has_identification))
    if project_id is not None:
        qs = qs.filter(project_id=project_id)

    if dry_run:
        count = qs.count()
        return f"Would clear determination_score on {count} human-determined occurrences"

    updated = qs.update(determination_score=None)
    return f"Cleared determination_score on {updated} human-determined occurrences"


class Command(BaseCommand):
    help = "Backfill determination_score=None on occurrences determined by a human identification"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report the count without writing")
        parser.add_argument("--project", type=int, default=None, help="Limit to a single project id")

    def handle(self, *args, **options):
        msg = backfill_human_determination_scores(
            dry_run=options["dry_run"],
            project_id=options["project"],
        )
        self.stdout.write(msg)
