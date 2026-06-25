"""
Seed synthetic Detections + Occurrences against an existing deployment so the
24h-cap regrouping path can be exercised on staging without running an ML
pipeline.

Each SourceImage in the deployment gets one Detection. Each Detection gets one
Occurrence (event=None, determination=None). After seeding, run
``group_images_into_events`` against the deployment with
``max_event_duration=timedelta(hours=24)`` and verify that
``Occurrence.event_id`` is populated correctly via the realignment Subquery.

Usage:
    docker compose exec django python manage.py seed_synthetic_occurrences \
        --deployment <id> [--limit 5000] [--batch-size 1000] [--clean]
"""

import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ami.main.models import Deployment, Detection, Occurrence, SourceImage


class Command(BaseCommand):
    help = "Create synthetic Detections + Occurrences for a deployment to test event_id realignment."

    def add_arguments(self, parser):
        parser.add_argument("--deployment", type=int, required=True, help="Deployment PK")
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Max number of SourceImages to seed against (default: all)",
        )
        parser.add_argument("--batch-size", type=int, default=1000)
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Delete synthetic Detections + Occurrences for this deployment instead of creating",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print counts without writing",
        )

    def handle(self, *args, **opts):
        try:
            deployment = Deployment.objects.get(pk=opts["deployment"])
        except Deployment.DoesNotExist as exc:
            raise CommandError(f"Deployment {opts['deployment']} not found") from exc

        if opts["clean"]:
            self._clean(deployment, dry_run=opts["dry_run"])
            return

        self._seed(
            deployment=deployment,
            limit=opts["limit"],
            batch_size=opts["batch_size"],
            dry_run=opts["dry_run"],
        )

    def _seed(self, deployment: Deployment, limit: int | None, batch_size: int, dry_run: bool) -> None:
        qs = SourceImage.objects.filter(deployment=deployment).order_by("pk")
        if limit:
            qs = qs[:limit]

        total = qs.count()
        if not total:
            self.stdout.write(self.style.WARNING(f"No SourceImages on deployment {deployment.pk}"))
            return

        self.stdout.write(
            f"Seeding {total} SourceImages on deployment {deployment.pk} "
            f"({deployment.project_id=}) in batches of {batch_size}"
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run; no writes."))
            return

        created_detections = 0
        created_occurrences = 0
        for offset in range(0, total, batch_size):
            batch = list(qs[offset : offset + batch_size].values("pk", "timestamp"))
            with transaction.atomic():
                occurrences = Occurrence.objects.bulk_create(
                    [
                        Occurrence(
                            project_id=deployment.project_id,
                            deployment_id=deployment.pk,
                            event=None,
                            determination=None,
                        )
                        for _ in batch
                    ]
                )
                detections = [
                    Detection(
                        source_image_id=row["pk"],
                        timestamp=row["timestamp"],
                        bbox=[10, 10, 20, 20],
                        occurrence_id=occ.pk,
                    )
                    for row, occ in zip(batch, occurrences)
                ]
                Detection.objects.bulk_create(detections)
            created_occurrences += len(occurrences)
            created_detections += len(detections)
            self.stdout.write(f"  ...batch {offset // batch_size + 1}: {len(batch)} rows")

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_detections} Detections + {created_occurrences} Occurrences "
                f"on deployment {deployment.pk}. Now run group_images_into_events with "
                f"max_event_duration={datetime.timedelta(hours=24)} and confirm event_id realignment."
            )
        )

    def _clean(self, deployment: Deployment, dry_run: bool) -> None:
        synthetic_dets = Detection.objects.filter(
            source_image__deployment=deployment,
            bbox=[10, 10, 20, 20],
            detection_algorithm__isnull=True,
            path__isnull=True,
        )
        synthetic_occ_ids = list(
            synthetic_dets.exclude(occurrence__isnull=True).values_list("occurrence_id", flat=True).distinct()
        )

        det_count = synthetic_dets.count()
        occ_count = Occurrence.objects.filter(pk__in=synthetic_occ_ids).count()

        self.stdout.write(
            f"Would delete {det_count} synthetic Detections + {occ_count} Occurrences on deployment {deployment.pk}"
        )
        if dry_run:
            return

        with transaction.atomic():
            synthetic_dets.delete()
            Occurrence.objects.filter(pk__in=synthetic_occ_ids).delete()
        self.stdout.write(self.style.SUCCESS("Cleaned."))
