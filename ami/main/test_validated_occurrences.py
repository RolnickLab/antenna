"""Replaying confirmed occurrences and identifications onto another project.

Every test exports from one project and imports into a second one that holds the same
captures and boxes but, as a pipeline leaves them, one occurrence per detection and no
confirmations. What a replay must preserve: the reviewer and time of each confirmation,
the user and time of each identification, and the rule that a partially found occurrence
is never confirmed.
"""

import dataclasses
import datetime
import pathlib
import tempfile

import numpy as np
from django.test import TestCase

from ami.main.models import (
    Detection,
    Identification,
    Occurrence,
    SourceImage,
    Taxon,
    TaxonRank,
    User,
    group_images_into_events,
)
from ami.main.models_future.detection_matching import MATCH_EXACT, MATCH_IOU, MATCH_NO_CANDIDATE, bbox_iou
from ami.main.models_future.embedding_transfer import (
    EmbeddingManifest,
    embedding_model,
    export_embeddings,
    import_embeddings,
    read_index,
)
from ami.main.models_future.tracks import verify_grouping
from ami.main.models_future.validated_occurrences import (
    OUTCOME_APPLIED,
    OUTCOME_PARTIAL,
    OUTCOME_UNCHANGED,
    Bundle,
    ImportOptions,
    build_bundle,
    import_bundle,
    occurrence_detection_keys,
)
from ami.ml.models import Algorithm
from ami.tests.fixtures.main import create_taxa, setup_test_project
from ami.tests.fixtures.tracking import pgvector_is_available

CONFIRMED_AT = datetime.datetime(2024, 6, 10, 9, 30, 0)
IDENTIFIED_AT = datetime.datetime(2024, 6, 9, 8, 0, 0)
WITHDRAWN_AT = datetime.datetime(2024, 6, 8, 8, 0, 0)
TRACK_BOX = [10.0, 10.0, 40.0, 40.0]
OTHER_BOX = [100.0, 100.0, 140.0, 140.0]


class ReplayTestCase(TestCase):
    def setUp(self) -> None:
        self.source_project, self.source_deployment = setup_test_project(reuse=False)
        self.target_project, self.target_deployment = setup_test_project(reuse=False)
        create_taxa(self.source_project)
        self.taxon, self.other_taxon = list(
            Taxon.objects.filter(rank=TaxonRank.SPECIES.name, projects=self.source_project).order_by("pk")[:2]
        )
        self.reviewer = User.objects.create_user(email="reviewer@example.org", name="Reviewer")  # type: ignore
        self.identifier = User.objects.create_user(email="identifier@example.org")  # type: ignore[attr-defined]
        self.source_captures = self._make_captures(self.source_deployment)
        self.target_captures = self._make_captures(self.target_deployment)
        self.track, self.identified = self._make_source_occurrences()

    def _make_captures(self, deployment) -> list[SourceImage]:
        start = datetime.datetime(2024, 6, 1, 22, 0)
        captures = [
            SourceImage.objects.create(
                deployment=deployment,
                project=deployment.project,
                timestamp=start + datetime.timedelta(minutes=i),
                path=f"replay/capture-{i}.jpg",
                width=640,
                height=480,
            )
            for i in range(6)
        ]
        group_images_into_events(deployment)
        for capture in captures:
            capture.refresh_from_db()
        return captures

    def _make_source_occurrences(self) -> tuple[Occurrence, Occurrence]:
        """A confirmed four-frame track with two identifications, and an identified two-frame occurrence."""
        track = self._occurrence_with_boxes(self.source_project, self.source_captures[:4], TRACK_BOX)
        Identification.objects.create(occurrence=track, user=self.identifier, taxon=self.other_taxon)
        Identification.objects.filter(occurrence=track).update(created_at=WITHDRAWN_AT, updated_at=WITHDRAWN_AT)
        Identification.objects.create(occurrence=track, user=self.identifier, taxon=self.taxon, comment="sure")
        Identification.objects.filter(occurrence=track, taxon=self.taxon).update(
            created_at=IDENTIFIED_AT, updated_at=IDENTIFIED_AT
        )
        verify_grouping(track, self.reviewer)
        Occurrence.objects.filter(pk=track.pk).update(grouping_verified_at=CONFIRMED_AT)

        identified = self._occurrence_with_boxes(self.source_project, self.source_captures[4:], OTHER_BOX)
        Identification.objects.create(occurrence=identified, user=self.reviewer, taxon=self.taxon)
        Identification.objects.filter(occurrence=identified).update(created_at=IDENTIFIED_AT, updated_at=IDENTIFIED_AT)
        return Occurrence.objects.get(pk=track.pk), Occurrence.objects.get(pk=identified.pk)

    def _occurrence_with_boxes(self, project, captures, bbox) -> Occurrence:
        occurrence = Occurrence.objects.create(
            event=captures[0].event, deployment=captures[0].deployment, project=project
        )
        for capture in captures:
            Detection.objects.create(
                source_image=capture, timestamp=capture.timestamp, bbox=bbox, occurrence=occurrence
            )
        occurrence.save()
        return occurrence

    def _populate_target(self, shift: float = 0.0, skip_capture_index: int | None = None) -> None:
        """One occurrence per detection, the way a detector run leaves a project."""
        for index, capture in enumerate(self.target_captures):
            if index == skip_capture_index:
                continue
            bbox = [coordinate + shift for coordinate in (TRACK_BOX if index < 4 else OTHER_BOX)]
            self._occurrence_with_boxes(self.target_project, [capture], bbox)

    def _replay(self, **options) -> tuple[Bundle, object]:
        bundle = Bundle.from_dict(build_bundle(self.source_project).as_dict())
        return bundle, import_bundle(self.target_project, bundle, ImportOptions(**options))

    def _target_track(self) -> Occurrence:
        return Occurrence.objects.get(project=self.target_project, grouping_verified_at__isnull=False)


class TestReplayConfirmedOccurrences(ReplayTestCase):
    def test_the_bundle_names_detections_by_capture_and_box_only(self):
        bundle = build_bundle(self.source_project)

        self.assertEqual({record.ref for record in bundle.occurrences}, {str(self.track.pk), str(self.identified.pk)})
        track = next(record for record in bundle.occurrences if record.ref == str(self.track.pk))
        self.assertEqual([key.capture_path for key in track.detections], [c.path for c in self.source_captures[:4]])
        self.assertEqual(track.detections[0].bbox, tuple(TRACK_BOX))
        self.assertEqual(track.confirmation.user_email, self.reviewer.email)
        self.assertEqual(track.confirmation.verified_at, CONFIRMED_AT.isoformat())
        self.assertEqual(len(track.identifications), 2)

    def test_a_round_trip_rebuilds_the_track_under_the_original_reviewer_and_time(self):
        self._populate_target()

        _, report = self._replay(execute=True)

        self.assertEqual(report.summary()["detections"], {MATCH_EXACT: 6})
        self.assertEqual(report.outcome_counts(), {OUTCOME_APPLIED: 2})
        rebuilt = self._target_track()
        self.assertEqual(
            [key.capture_path for key in occurrence_detection_keys(rebuilt)],
            [c.path for c in self.target_captures[:4]],
        )
        self.assertEqual(rebuilt.grouping_verified_at, CONFIRMED_AT, "The confirmation keeps the exported time")
        self.assertEqual(rebuilt.grouping_verified_by, self.reviewer)
        self.assertEqual(Occurrence.objects.filter(project=self.target_project).count(), 3, "4 singles became 1 track")

    def test_identifications_keep_their_user_time_and_withdrawn_state(self):
        self._populate_target()

        self._replay(execute=True)

        rebuilt = self._target_track()
        current = Identification.objects.get(occurrence=rebuilt, withdrawn=False)
        self.assertEqual(
            (current.user, current.taxon, current.created_at, current.comment),
            (self.identifier, self.taxon, IDENTIFIED_AT, "sure"),
        )
        withdrawn = Identification.objects.get(occurrence=rebuilt, withdrawn=True)
        self.assertEqual((withdrawn.taxon, withdrawn.created_at), (self.other_taxon, WITHDRAWN_AT))
        self.assertEqual(rebuilt.determination, self.taxon)
        other = Identification.objects.get(user=self.reviewer, occurrence__project=self.target_project)
        self.assertEqual(other.occurrence.detections.first().source_image.path, self.target_captures[4].path)
        self.assertIsNone(other.occurrence.grouping_verified_at, "An identified-only occurrence is not confirmed")

    def test_boxes_that_moved_a_little_match_by_overlap(self):
        self._populate_target(shift=2.0)
        self.assertGreater(bbox_iou(TRACK_BOX, [c + 2.0 for c in TRACK_BOX]), 0.7)

        _, report = self._replay(execute=True)

        self.assertEqual(report.summary()["detections"], {MATCH_IOU: 6})
        self.assertEqual(self._target_track().grouping_verified_at, CONFIRMED_AT)

    def test_a_stricter_overlap_threshold_leaves_moved_boxes_unmatched(self):
        self._populate_target(shift=2.0)

        _, report = self._replay(execute=True, iou_threshold=0.9)

        self.assertEqual(report.summary()["detections"], {MATCH_NO_CANDIDATE: 6})
        self.assertEqual(report.outcome_counts(), {OUTCOME_PARTIAL: 2})
        self.assertFalse(
            Occurrence.objects.filter(project=self.target_project, grouping_verified_at__isnull=False).exists()
        )

    def test_an_occurrence_with_a_missing_detection_is_reported_partial_and_not_confirmed(self):
        self._populate_target(skip_capture_index=2)

        _, report = self._replay(execute=True)

        track_outcome = next(o for o in report.outcomes if o.ref == str(self.track.pk))
        self.assertEqual(track_outcome.outcome, OUTCOME_PARTIAL)
        self.assertEqual(track_outcome.match_counts, {MATCH_EXACT: 3, MATCH_NO_CANDIDATE: 1})
        self.assertFalse(track_outcome.confirmed)
        self.assertFalse(
            Occurrence.objects.filter(project=self.target_project, grouping_verified_at__isnull=False).exists()
        )
        self.assertEqual(
            Occurrence.objects.filter(project=self.target_project).count(), 5, "The grouping was left alone"
        )
        self.assertEqual(
            track_outcome.identifications_applied, 2, "What people said still lands on the nearest occurrence"
        )

    def test_a_hand_drawn_box_can_be_recreated_on_its_capture(self):
        self._populate_target(skip_capture_index=2)

        _, report = self._replay(execute=True, create_missing_detections=True)

        track_outcome = next(o for o in report.outcomes if o.ref == str(self.track.pk))
        self.assertEqual((track_outcome.outcome, track_outcome.created), (OUTCOME_APPLIED, 1))
        rebuilt = self._target_track()
        self.assertEqual(rebuilt.detections.count(), 4)
        recreated = rebuilt.detections.get(source_image=self.target_captures[2])
        self.assertEqual((recreated.bbox, recreated.timestamp), (TRACK_BOX, self.target_captures[2].timestamp))

    def test_rerunning_the_import_changes_nothing(self):
        self._populate_target()
        self._replay(execute=True)
        before = (
            Occurrence.objects.filter(project=self.target_project).count(),
            Identification.objects.filter(occurrence__project=self.target_project).count(),
            self._target_track().grouping_verified_at,
        )

        _, report = self._replay(execute=True)

        self.assertEqual(report.outcome_counts(), {OUTCOME_UNCHANGED: 2})
        self.assertEqual(report.summary()["identifications_skipped"], 3)
        self.assertEqual(report.summary()["identifications_applied"], 0)
        after = (
            Occurrence.objects.filter(project=self.target_project).count(),
            Identification.objects.filter(occurrence__project=self.target_project).count(),
            self._target_track().grouping_verified_at,
        )
        self.assertEqual(before, after)

    def test_a_dry_run_reports_the_plan_and_writes_nothing(self):
        self._populate_target()

        _, report = self._replay(execute=False)

        self.assertEqual(report.outcome_counts(), {OUTCOME_APPLIED: 2})
        self.assertEqual(report.summary()["detections"], {MATCH_EXACT: 6})
        self.assertTrue(next(o for o in report.outcomes if o.ref == str(self.track.pk)).confirmed, "would confirm")
        self.assertEqual(Occurrence.objects.filter(project=self.target_project).count(), 6)
        self.assertFalse(Identification.objects.filter(occurrence__project=self.target_project).exists())

    def test_a_missing_reviewer_or_taxon_is_reported_and_skipped(self):
        self._populate_target()
        bundle = build_bundle(self.source_project)
        track = next(record for record in bundle.occurrences if record.ref == str(self.track.pk))
        track.confirmation.user_email = "nobody@example.org"
        first = track.identifications[0]
        track.identifications[0] = dataclasses.replace(
            first, taxon=dataclasses.replace(first.taxon, name="Not a real taxon", gbif_taxon_key=None)
        )

        report = import_bundle(self.target_project, bundle, ImportOptions(execute=True))

        self.assertEqual(report.missing_users, ["nobody@example.org"])
        self.assertEqual([t["name"] for t in report.missing_taxa], ["Not a real taxon"])
        track_outcome = next(o for o in report.outcomes if o.ref == str(self.track.pk))
        self.assertFalse(track_outcome.confirmed)
        self.assertEqual((track_outcome.identifications_applied, track_outcome.identifications_skipped), (1, 1))


class TestEmbeddingTransfer(ReplayTestCase):
    def setUp(self) -> None:
        if not pgvector_is_available():
            self.skipTest("pgvector is not installed in this database")
        super().setUp()
        self.algorithm = Algorithm.objects.create(key="replay-test-backbone", name="Replay Test Backbone")
        rng = np.random.default_rng(7)
        self.vectors = {}
        for detection in Detection.objects.filter(source_image__project=self.source_project):
            vector = rng.standard_normal(2048).astype(np.float32)
            detection.classifications.create(
                taxon=self.taxon,
                score=0.5,
                algorithm=self.algorithm,
                timestamp=detection.timestamp,
                features_2048=vector.tolist(),
            )
            self.vectors[detection.source_image.path] = vector

    def test_vectors_round_trip_by_detection_key(self):
        self._populate_target()
        with tempfile.TemporaryDirectory() as directory:
            directory = pathlib.Path(directory)
            manifest = export_embeddings(self.source_project, self.algorithm, directory)

            self.assertEqual(
                (manifest.count, manifest.dimensions, manifest.algorithm_key), (6, 2048, "replay-test-backbone")
            )
            self.assertEqual(EmbeddingManifest.read(directory).count, 6)
            keys = read_index(directory)
            matrix = np.load(directory / "vectors.npy")
            for row, key in enumerate(keys):
                np.testing.assert_array_equal(matrix[row], self.vectors[key.capture_path])

            report = import_embeddings(self.target_project, directory, execute=False)
            self.assertEqual(report.summary()["detections"], {MATCH_EXACT: 6})

            if embedding_model() is None:
                with self.assertRaises(RuntimeError):
                    import_embeddings(self.target_project, directory, execute=True)
                return
            report = import_embeddings(self.target_project, directory, execute=True)
            self.assertEqual(report.written, 6)
            again = import_embeddings(self.target_project, directory, execute=True)
            self.assertEqual((again.written, again.skipped_existing), (0, 6))
