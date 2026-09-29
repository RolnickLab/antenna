import io
import logging

from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from ami.main.models import Classification, Detection, Identification, Occurrence, Taxon
from ami.main.models_future.session_reset import SessionResetRefused, reset_session_tracking, session_tracking_counts
from ami.main.tests import cachalot_disabled
from ami.ml.models import Algorithm
from ami.ml.post_processing.tracking_task import assign_occurrences_from_detection_chains, event_is_fresh
from ami.tests.fixtures.main import create_captures, create_occurrences, create_taxa, setup_test_project
from ami.users.tests.factories import UserFactory

logger = logging.getLogger(__name__)


class TestResetSessionTracking(TestCase):
    """A reset returns a tracked session to one occurrence per detection, so it can be tracked again."""

    def _build_tracked_session(self, images: int, boxes_per_image: int = 2):
        """A session whose detections each predict their own taxon, tracked into one chain per box
        position, with one grouping confirmation and the tracking task's recorded classifications."""
        project, deployment = setup_test_project(reuse=False)
        create_captures(deployment=deployment, num_nights=1, images_per_night=images, interval_minutes=1)
        create_taxa(project)
        create_occurrences(deployment=deployment, num=images * boxes_per_image)
        event = project.events.get()
        captures = list(event.captures.order_by("timestamp"))
        taxa = list(Taxon.objects.filter(projects=project).order_by("pk"))

        detections_by_capture = [list(c.detections.order_by("pk")) for c in captures]
        for i, detection in enumerate(det for dets in detections_by_capture for det in dets):
            Classification.objects.filter(detection=detection).update(
                taxon=taxa[i % len(taxa)], score=0.5 + (i % 7) / 20, terminal=True
            )
        for position in range(boxes_per_image):
            chain = [dets[position] for dets in detections_by_capture]
            for current, following in zip(chain, chain[1:]):
                current.next_detection = following
                current.save(update_fields=["next_detection"])

        tracking = Algorithm.objects.get_or_create(key="tracking", defaults={"name": "Occurrence Tracking"})[0]
        assign_occurrences_from_detection_chains(captures, logger, record_as=tracking)
        keeper = Occurrence.objects.filter(event=event).order_by("pk").first()
        Occurrence.objects.filter(pk=keeper.pk).update(
            grouping_verified_at=timezone.now(), grouping_verified_by=UserFactory()
        )
        return project, event

    def test_splits_every_track_and_clears_links_verification_and_tracking_records(self):
        project, event = self._build_tracked_session(images=4)
        tracked = session_tracking_counts(event)
        self.assertEqual((tracked.occurrences, tracked.multi_detection_occurrences), (2, 2))
        self.assertEqual((tracked.links, tracked.grouping_verified), (6, 1))

        result = reset_session_tracking(event)

        self.assertEqual((result.occurrences_split, result.occurrences_created), (2, 6))
        after = session_tracking_counts(event)
        self.assertEqual((after.occurrences, after.multi_detection_occurrences), (8, 0))
        self.assertEqual((after.links, after.grouping_verified), (0, 0))
        self.assertTrue(event_is_fresh(event)[0])
        self.assertFalse(Classification.objects.filter(algorithm__key="tracking").exists())
        for occurrence in Occurrence.objects.filter(detections__source_image__event=event):
            best = occurrence.best_prediction
            self.assertEqual(
                (occurrence.determination_id, occurrence.determination_score), (best.taxon_id, best.score)
            )

    def test_refuses_a_session_with_identifications_unless_forced(self):
        project, event = self._build_tracked_session(images=3)
        occurrence = Occurrence.objects.filter(event=event).order_by("pk").first()
        Identification.objects.create(occurrence=occurrence, user=UserFactory(), taxon=occurrence.determination)

        with self.assertRaises(SessionResetRefused):
            reset_session_tracking(event)
        self.assertEqual(session_tracking_counts(event).multi_detection_occurrences, 2)

        result = reset_session_tracking(event, force=True)
        self.assertEqual(result.after.multi_detection_occurrences, 0)
        self.assertEqual(Identification.objects.filter(occurrence=occurrence).count(), 1)

    def test_dry_run_reports_the_plan_and_writes_nothing(self):
        project, event = self._build_tracked_session(images=3)
        links = dict(Detection.objects.filter(source_image__event=event).values_list("pk", "next_detection_id"))
        memberships = dict(Detection.objects.filter(source_image__event=event).values_list("pk", "occurrence_id"))
        before = session_tracking_counts(event)

        out = io.StringIO()
        call_command("reset_tracking", project=project.pk, events=[event.pk], dry_run=True, stdout=out)

        self.assertIn("'occurrences_created': 4", out.getvalue())
        self.assertEqual(session_tracking_counts(event), before)
        self.assertEqual(
            dict(Detection.objects.filter(source_image__event=event).values_list("pk", "next_detection_id")), links
        )
        self.assertEqual(
            dict(Detection.objects.filter(source_image__event=event).values_list("pk", "occurrence_id")),
            memberships,
        )

    def test_command_rejects_a_session_from_another_project(self):
        project, event = self._build_tracked_session(images=2)
        with self.assertRaises(CommandError):
            call_command("reset_tracking", project=project.pk + 1000, events=[event.pk], stdout=io.StringIO())

    def test_query_count_does_not_grow_with_the_session(self):
        """Doubling the detections must not add queries: every write is a bulk statement."""
        counts = []
        for images in (3, 6):
            project, event = self._build_tracked_session(images=images)
            with cachalot_disabled(), CaptureQueriesContext(connection) as context:
                reset_session_tracking(event)
            counts.append(len(context.captured_queries))
        self.assertEqual(counts[0], counts[1], counts)
