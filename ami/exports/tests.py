import csv
import json
import logging

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase
from rest_framework.test import APIClient

from ami.exports.models import DataExport
from ami.main.models import Detection, Identification, Occurrence, SourceImageCollection, Taxon
from ami.ml.models import Algorithm
from ami.tests.fixtures.main import (
    create_captures,
    create_occurrences,
    create_taxa,
    group_images_into_events,
    setup_test_project,
)

logger = logging.getLogger(__name__)


class DataExportTest(TestCase):
    def setUp(self):
        self.project, self.deployment = setup_test_project(reuse=False)
        self.user = self.project.owner
        self.assertIsNotNone(self.user, "Project owner should not be None.")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        # Create captures & occurrences to test exporting
        create_captures(deployment=self.deployment, num_nights=2, images_per_night=4, interval_minutes=1)
        group_images_into_events(self.deployment)
        create_taxa(self.project)
        create_occurrences(num=10, deployment=self.deployment)
        # Assert project has occurrences
        self.assertGreater(self.project.occurrences.count(), 0, "No occurrences created for testing.")
        # Create a collection using the provided method
        self.collection = self._create_collection()
        # Define export formats
        self.export_formats = ["occurrences_simple_csv", "occurrences_api_json"]

    def _create_export_with_file(self, format_type):
        filename = f"exports/test_export_file_{format_type}.json"
        default_storage.save(filename, ContentFile(b"Dummy content"))

        export = DataExport.objects.create(
            user=self.user,
            project=self.project,
            format=format_type,
            file_url=filename,
        )

        return export, filename

    def test_file_is_deleted_when_export_is_deleted(self):
        for format_type in self.export_formats:
            with self.subTest(format=format_type):
                export, filename = self._create_export_with_file(format_type)

                self.assertTrue(default_storage.exists(filename))

                response = self.client.delete(f"/api/v2/exports/{export.pk}/")
                self.assertEqual(response.status_code, 204)

                self.assertFalse(default_storage.exists(filename))

    def _create_collection(self):
        """Create a SourceImageCollection from deployment captures."""
        images = self.project.captures.all()
        # Use only half of the images for the collection
        collection_images = images[: images.count() // 2]

        # Ensure collection images are fewer than total images
        self.assertGreater(len(collection_images), 0, "No collection images to test exports.")
        self.assertLess(len(collection_images), images.count(), "Collection images should be fewer than total images.")

        # Create the collection
        collection = SourceImageCollection.objects.create(
            name="Test Manual Source Image Collection",
            project=self.project,
            method="manual",
            kwargs={"image_ids": [image.pk for image in collection_images]},
        )
        collection.save()

        # Populate the collection sample
        collection.populate_sample()
        return collection

    def run_and_validate_export(self, format_type):
        """Run export and validate record count in the exported file."""
        # Create a DataExport instance
        data_export = DataExport.objects.create(
            user=self.user,
            project=self.project,
            format=format_type,
            filters={"collection_id": self.collection.pk},
            job=None,
        )

        # Run export and get the file URL
        file_url = data_export.run_export()

        # Ensure the file is generated
        self.assertIsNotNone(file_url)
        file_path = file_url.replace("/media/", "")
        self.assertTrue(default_storage.exists(file_path))

        # Read and validate the exported data
        with default_storage.open(file_path, "r") as f:
            if format_type == "occurrences_simple_csv":
                self.validate_csv_records(f)
            elif format_type == "occurrences_api_json":
                self.validate_json_records(f)

        # Clean up the exported file after the test
        default_storage.delete(file_path)

    def test_export_record_count(self):
        """Test record count in the exported file."""
        for format_type in self.export_formats:
            with self.subTest(format=format_type):
                self.run_and_validate_export(format_type)

    def validate_record_count(self, record_count):
        """Validate record count in the exported file."""
        collection_count = (
            Occurrence.objects.valid()  # type: ignore[union-attr] # Custom queryset method
            .filter(detections__source_image__collections=self.collection)
            .distinct()
            .count()
        )
        total_count = Occurrence.objects.valid().filter(project=self.project).count()  # type: ignore[union-attr]

        logger.debug(f"Exported: {record_count}, # in Collection: {collection_count}, # in Project: {total_count}")
        self.assertGreater(record_count, 0, "Record count should be greater than zero.")
        self.assertLess(record_count, total_count, "Record count should be less than total occurrences.")
        self.assertEqual(record_count, collection_count, "Record count does not match expected count.")

    def validate_csv_records(self, file):
        """Validate record count in CSV."""
        csv_reader = csv.DictReader(file)
        row_count = sum(1 for row in csv_reader)
        self.validate_record_count(row_count)

    def validate_json_records(self, file):
        """Validate record count in JSON."""
        data = json.load(file)
        self.validate_record_count(len(data))

    def test_csv_export_record_count(self):
        """Test CSV export record count."""
        self.run_and_validate_export("occurrences_simple_csv")

    def test_json_export_record_count(self):
        """Test JSON export record count."""
        self.run_and_validate_export("occurrences_api_json")

    def test_csv_export_has_detection_fields(self):
        """Test that CSV export includes best detection fields."""
        # Create a DataExport instance
        data_export = DataExport.objects.create(
            user=self.user,
            project=self.project,
            format="occurrences_simple_csv",
            filters={"collection_id": self.collection.pk},
            job=None,
        )

        # Run export and get the file URL
        file_url = data_export.run_export()

        # Ensure the file is generated
        self.assertIsNotNone(file_url)
        file_path = file_url.replace("/media/", "")
        self.assertTrue(default_storage.exists(file_path))

        # Read and validate the exported data
        with default_storage.open(file_path, "r") as f:
            csv_reader = csv.DictReader(f)
            rows = list(csv_reader)

            # Ensure we have rows to test
            self.assertGreater(len(rows), 0, "No rows exported")

            # Check that the new fields are present in the header
            first_row = rows[0]
            self.assertIn("best_detection_url", first_row.keys(), "best_detection_url field missing from CSV")
            self.assertIn("best_detection_width", first_row.keys(), "best_detection_width field missing from CSV")
            self.assertIn("best_detection_height", first_row.keys(), "best_detection_height field missing from CSV")

            # Check that at least one row has non-empty values for the new fields
            # (Some occurrences might not have detections, so we check if any row has values)
            has_url = any(row.get("best_detection_url") for row in rows)
            has_dimensions = any(row.get("best_detection_width") and row.get("best_detection_height") for row in rows)

            # Assert that at least one row has detection data
            self.assertTrue(
                has_url,
                f"No detection URLs found in {len(rows)} exported rows. "
                "At least one occurrence should have a detection URL.",
            )
            self.assertTrue(
                has_dimensions,
                f"No detection dimensions found in {len(rows)} exported rows. "
                "At least one occurrence should have detection width and height.",
            )

        # Clean up the exported file after the test
        default_storage.delete(file_path)


class DataExportPermissionTest(TestCase):
    """Test data export permissions (create, update, delete)."""

    def setUp(self):
        self.project, self.deployment = setup_test_project(reuse=False)
        self.owner = self.project.owner

        # Create a researcher (project member with Researcher role)
        from ami.users.models import User
        from ami.users.roles import Researcher

        self.researcher = User.objects.create_user(email="researcher@test.org")
        self.project.members.add(self.researcher)
        Researcher.assign_user(self.researcher, self.project)

        # Create a basic member (no Researcher role)
        from ami.users.roles import BasicMember

        self.basic_member = User.objects.create_user(email="basic@test.org")
        self.project.members.add(self.basic_member)
        BasicMember.assign_user(self.basic_member, self.project)

        # Create a superuser
        self.superuser = User.objects.create_superuser(email="super@test.org", password="test123")

        # Create a non-member
        self.non_member = User.objects.create_user(email="nonmember@test.org")

        self.client = APIClient()

    def _create_export(self, user):
        """Helper to create an export owned by the given user."""
        return DataExport.objects.create(
            user=user,
            project=self.project,
            format="occurrences_simple_csv",
        )

    def test_researcher_can_create_export(self):
        """Researcher role should be able to create data exports."""
        from ami.main.models import Project

        self.assertTrue(
            self.researcher.has_perm(Project.Permissions.CREATE_DATA_EXPORT, self.project),
            "Researcher should have create_dataexport permission",
        )

    def test_researcher_can_delete_export(self):
        """Researcher role should be able to delete data exports."""
        from ami.main.models import Project

        self.assertTrue(
            self.researcher.has_perm(Project.Permissions.DELETE_DATA_EXPORT, self.project),
            "Researcher should have delete_dataexport permission",
        )

    def test_researcher_cannot_update_export(self):
        """Researcher role should NOT be able to update data exports (admin-only)."""
        from ami.main.models import Project

        self.assertFalse(
            self.researcher.has_perm(Project.Permissions.UPDATE_DATA_EXPORT, self.project),
            "Researcher should NOT have update_dataexport permission (admin-only)",
        )

    def test_basic_member_cannot_create_export(self):
        """Basic member (without Researcher role) should not be able to create exports."""
        from ami.main.models import Project

        self.assertFalse(
            self.basic_member.has_perm(Project.Permissions.CREATE_DATA_EXPORT, self.project),
            "Basic member should not have create_dataexport permission",
        )

    def test_superuser_can_update_export(self):
        """Superuser should be able to update data exports."""
        from ami.main.models import Project

        # Superusers bypass object-level permissions via has_perm
        self.assertTrue(
            self.superuser.has_perm(Project.Permissions.UPDATE_DATA_EXPORT, self.project),
            "Superuser should have update_dataexport permission",
        )

    def test_non_member_cannot_create_export(self):
        """Non-members should not be able to create exports."""
        from ami.main.models import Project

        self.assertFalse(
            self.non_member.has_perm(Project.Permissions.CREATE_DATA_EXPORT, self.project),
            "Non-member should not have create_dataexport permission",
        )


class ExportNewFieldsTest(TestCase):
    """Test the new machine prediction, verification, and detection fields in CSV exports."""

    def setUp(self):
        self.project, self.deployment = setup_test_project(reuse=False)
        self.user = self.project.owner
        self.user.name = "Test Verifier"
        self.user.save()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        create_captures(deployment=self.deployment, num_nights=1, images_per_night=4, interval_minutes=1)
        group_images_into_events(self.deployment)
        create_taxa(self.project)

        # Create an algorithm for classifications
        self.algorithm, _ = Algorithm.objects.get_or_create(
            name="test-classifier",
            defaults={"key": "test-classifier"},
        )

        # Create a second taxon for disagreement tests
        self.taxa = list(Taxon.objects.filter(projects=self.project)[:2])
        self.taxon_a = self.taxa[0]
        if len(self.taxa) > 1:
            self.taxon_b = self.taxa[1]
        else:
            self.taxon_b = Taxon.objects.create(name="Test Taxon B")
            self.taxon_b.projects.add(self.project)

    def _create_occurrence_with_prediction(self, taxon=None, score=0.85):
        """Create an occurrence with a single detection and ML classification."""
        taxon = taxon or self.taxon_a
        source_image = self.project.captures.first()
        detection = Detection.objects.create(
            source_image=source_image,
            timestamp=source_image.timestamp,
            bbox=[0.1, 0.1, 0.5, 0.5],
            path="detections/test.jpg",
        )
        classification = detection.classifications.create(
            taxon=taxon,
            score=score,
            timestamp=source_image.timestamp,
            algorithm=self.algorithm,
            terminal=True,
        )
        occurrence = detection.associate_new_occurrence()
        return occurrence, classification

    def _run_csv_export(self):
        """Run a CSV export and return the rows as a list of dicts."""
        data_export = DataExport.objects.create(
            user=self.user,
            project=self.project,
            format="occurrences_simple_csv",
            job=None,
        )
        file_url = data_export.run_export()
        self.assertIsNotNone(file_url)
        file_path = file_url.replace("/media/", "")
        with default_storage.open(file_path, "r") as f:
            rows = list(csv.DictReader(f))
        default_storage.delete(file_path)
        return rows

    def test_ml_prediction_only(self):
        """Occurrence with only ML prediction: machine prediction fields populated, verified_by null."""
        occurrence, classification = self._create_occurrence_with_prediction()
        rows = self._run_csv_export()

        row = next(r for r in rows if int(r["id"]) == occurrence.pk)
        self.assertEqual(row["best_machine_prediction_name"], self.taxon_a.name)
        self.assertEqual(row["best_machine_prediction_algorithm"], "test-classifier")
        self.assertAlmostEqual(float(row["best_machine_prediction_score"]), 0.85, places=2)
        self.assertEqual(row["verified_by"], "")
        self.assertEqual(row["participant_count"], "0")

    def test_ml_prediction_with_agreeing_human(self):
        """Human agrees with ML: verified_by set, determination_matches = True."""
        occurrence, classification = self._create_occurrence_with_prediction()

        # Human agrees with the same taxon
        Identification.objects.create(
            user=self.user,
            taxon=self.taxon_a,
            occurrence=occurrence,
            agreed_with_prediction=classification,
        )

        rows = self._run_csv_export()
        row = next(r for r in rows if int(r["id"]) == occurrence.pk)

        # Machine prediction fields still populated
        self.assertEqual(row["best_machine_prediction_name"], self.taxon_a.name)
        self.assertAlmostEqual(float(row["best_machine_prediction_score"]), 0.85, places=2)

        # Verification fields
        verified_by = row["verified_by"]
        self.assertTrue(verified_by, "verified_by should not be empty")
        self.assertEqual(row["participant_count"], "1")
        self.assertEqual(row["agreed_with_algorithm"], "test-classifier")
        self.assertEqual(row["determination_matches_machine_prediction"], "True")

    def test_ml_prediction_with_disagreeing_human(self):
        """Human disagrees with ML: different determination, determination_matches = False."""
        occurrence, classification = self._create_occurrence_with_prediction(taxon=self.taxon_a)

        # Human identifies as a different taxon
        Identification.objects.create(
            user=self.user,
            taxon=self.taxon_b,
            occurrence=occurrence,
        )

        rows = self._run_csv_export()
        row = next(r for r in rows if int(r["id"]) == occurrence.pk)

        # Machine prediction still shows original
        self.assertEqual(row["best_machine_prediction_name"], self.taxon_a.name)
        # Determination is now the human's choice
        self.assertEqual(row["determination_name"], self.taxon_b.name)
        self.assertEqual(row["determination_matches_machine_prediction"], "False")
        self.assertEqual(row["agreed_with_algorithm"], "")

    def test_human_agrees_with_another_human(self):
        """User B agrees with user A's identification: agreed_with_user exposes A's email."""
        from ami.users.models import User

        user_a = User.objects.create_user(email="user-a@test.org")
        user_b = User.objects.create_user(email="user-b@test.org")

        occurrence, _ = self._create_occurrence_with_prediction()

        id_a = Identification.objects.create(
            user=user_a,
            taxon=self.taxon_b,
            occurrence=occurrence,
        )
        Identification.objects.create(
            user=user_b,
            taxon=self.taxon_b,
            occurrence=occurrence,
            agreed_with_identification=id_a,
        )

        rows = self._run_csv_export()
        row = next(r for r in rows if int(r["id"]) == occurrence.pk)

        self.assertEqual(row["agreed_with_user"], "user-a@test.org")
        # Not agreeing with an ML prediction
        self.assertEqual(row["agreed_with_algorithm"], "")

    def test_multiple_identifications_count(self):
        """Multiple identifications: verified_by_count reflects all non-withdrawn IDs."""
        occurrence, _ = self._create_occurrence_with_prediction()

        from ami.users.models import User

        user2 = User.objects.create_user(email="verifier2@test.org")

        Identification.objects.create(user=self.user, taxon=self.taxon_a, occurrence=occurrence)
        Identification.objects.create(user=user2, taxon=self.taxon_a, occurrence=occurrence)

        rows = self._run_csv_export()
        row = next(r for r in rows if int(r["id"]) == occurrence.pk)
        self.assertEqual(row["participant_count"], "2")

    def test_detection_bbox_field(self):
        """Best detection bbox is included in export."""
        occurrence, _ = self._create_occurrence_with_prediction()
        rows = self._run_csv_export()
        row = next(r for r in rows if int(r["id"]) == occurrence.pk)
        self.assertIn("best_detection_bbox", row)
        # bbox should be a string representation of the list
        self.assertIn("0.1", row["best_detection_bbox"])

    def test_api_and_csv_pick_same_best_prediction_with_mixed_terminal(self):
        """Occurrence.best_prediction and with_best_machine_prediction() must agree.

        With both a high-score non-terminal classification and a lower-score terminal
        classification, the terminal row should win in both the API's cached
        best_prediction and the CSV's annotated best_machine_prediction_* fields.
        """
        alg_intermediate, _ = Algorithm.objects.get_or_create(
            name="intermediate-classifier", defaults={"key": "intermediate-classifier"}
        )
        alg_terminal, _ = Algorithm.objects.get_or_create(
            name="terminal-classifier", defaults={"key": "terminal-classifier"}
        )
        source_image = self.project.captures.first()
        detection = Detection.objects.create(
            source_image=source_image,
            timestamp=source_image.timestamp,
            bbox=[0.1, 0.1, 0.5, 0.5],
            path="detections/mixed.jpg",
        )
        detection.classifications.create(
            taxon=self.taxon_a,
            score=0.95,
            timestamp=source_image.timestamp,
            algorithm=alg_intermediate,
            terminal=False,
        )
        detection.classifications.create(
            taxon=self.taxon_b,
            score=0.80,
            timestamp=source_image.timestamp,
            algorithm=alg_terminal,
            terminal=True,
        )
        occurrence = detection.associate_new_occurrence()

        rows = self._run_csv_export()
        row = next(r for r in rows if int(r["id"]) == occurrence.pk)

        self.assertEqual(row["best_machine_prediction_name"], self.taxon_b.name)
        self.assertEqual(row["best_machine_prediction_algorithm"], "terminal-classifier")
        self.assertAlmostEqual(float(row["best_machine_prediction_score"]), 0.80, places=2)

        occurrence.refresh_from_db()
        api_best = occurrence.best_prediction
        self.assertIsNotNone(api_best)
        self.assertEqual(api_best.taxon_id, self.taxon_b.pk)
        self.assertEqual(api_best.algorithm.name, "terminal-classifier")

    def test_csv_has_all_new_fields(self):
        """All new fields are present as CSV column headers."""
        self._create_occurrence_with_prediction()
        rows = self._run_csv_export()
        self.assertGreater(len(rows), 0)
        headers = rows[0].keys()
        expected_fields = [
            "best_machine_prediction_name",
            "best_machine_prediction_algorithm",
            "best_machine_prediction_score",
            "verified_by",
            "participant_count",
            "agreed_with_algorithm",
            "agreed_with_user",
            "determination_matches_machine_prediction",
            "best_detection_bbox",
            "best_detection_capture_url",
        ]
        for field in expected_fields:
            self.assertIn(field, headers, f"Missing CSV field: {field}")


class TracksExportTest(TestCase):
    """The tracks CSV: one row per detection, a fixed column contract, and bounded queries."""

    EXPECTED_HEADER = (
        "occurrence_id,detection_id,event_id,deployment_id,source_image_id,timestamp,frame_index,frame_count,"
        "bbox_x1,bbox_y1,bbox_x2,bbox_y2,image_width,image_height,detection_label,detection_score,"
        "occurrence_determination,occurrence_determination_score,grouping_verified,grouping_verified_at,"
        "has_feature_vector,next_detection_id"
    )

    def setUp(self):
        self.project, self.deployment = setup_test_project(reuse=False)
        self.user = self.project.owner
        create_captures(deployment=self.deployment, num_nights=1, images_per_night=3, interval_minutes=1)
        group_images_into_events(self.deployment)
        create_taxa(self.project)
        self.taxon = Taxon.objects.filter(projects=self.project).first()
        self.algorithm, _ = Algorithm.objects.get_or_create(
            name="test-classifier", defaults={"key": "test-classifier"}
        )
        self.captures = list(self.project.captures.order_by("timestamp"))
        self.captures[0].width, self.captures[0].height = 4096, 2160
        self.captures[0].save()
        # Three occurrences of three detections each, created latest frame first so that
        # the export cannot get frame order from detection pks.
        self.occurrences = [self._make_track(offset=i * 100) for i in range(3)]

    def _make_track(self, offset: int) -> Occurrence:
        occurrence = Occurrence.objects.create(
            project=self.project,
            deployment=self.deployment,
            event=self.captures[0].event,
            determination=self.taxon,
            determination_score=0.9,
        )
        for capture in reversed(self.captures):
            detection = Detection.objects.create(
                source_image=capture,
                timestamp=capture.timestamp,
                bbox=[offset, offset, offset + 10, offset + 20],
                occurrence=occurrence,
            )
            detection.classifications.create(
                taxon=self.taxon, score=0.8, timestamp=capture.timestamp, algorithm=self.algorithm, terminal=True
            )
        return occurrence

    def _rows(self, occurrences=None, **kwargs) -> list[dict[str, str]]:
        from ami.exports.tracks import iter_track_rows

        return list(iter_track_rows(occurrences or Occurrence.objects.filter(project=self.project), **kwargs))

    def _run_format_export(self) -> tuple[str, DataExport]:
        data_export = DataExport.objects.create(user=self.user, project=self.project, format="tracks_csv")
        file_path = data_export.run_export().replace("/media/", "")
        with default_storage.open(file_path, "r") as f:
            content = f.read()
        default_storage.delete(file_path)
        data_export.refresh_from_db()
        return content, data_export

    def test_format_export_header_is_the_contract(self):
        content, data_export = self._run_format_export()
        lines = content.splitlines()
        self.assertEqual(lines[0], self.EXPECTED_HEADER)
        self.assertEqual(len(lines) - 1, 9)
        self.assertEqual(data_export.record_count, 9, "A tracks export counts detection rows")

    def test_frame_index_follows_capture_time(self):
        rows = [row for row in self._rows() if row["occurrence_id"] == str(self.occurrences[0].pk)]
        by_capture = {int(row["source_image_id"]): row for row in rows}
        for index, capture in enumerate(self.captures):
            row = by_capture[capture.pk]
            self.assertEqual(row["frame_index"], str(index))
            self.assertEqual(row["frame_count"], "3")
            self.assertEqual(row["timestamp"], capture.timestamp.isoformat())
        first = by_capture[self.captures[0].pk]
        self.assertEqual((first["image_width"], first["image_height"]), ("4096", "2160"))
        self.assertEqual((first["bbox_x1"], first["bbox_y2"]), ("0", "20"))
        self.assertEqual((first["detection_label"], first["detection_score"]), (self.taxon.name, "0.8"))
        self.assertEqual(by_capture[self.captures[1].pk]["image_width"], "")

    def test_grouping_verified_flag(self):
        from django.utils import timezone

        verified = self.occurrences[1]
        verified.grouping_verified_at = timezone.now()
        verified.save(update_fields=["grouping_verified_at"])

        rows = self._rows()
        flags = {row["occurrence_id"]: (row["grouping_verified"], row["grouping_verified_at"]) for row in rows}
        self.assertEqual(flags[str(verified.pk)], ("true", verified.grouping_verified_at.isoformat()))
        self.assertEqual(flags[str(self.occurrences[0].pk)], ("false", ""))

    def test_feature_vector_and_next_detection(self):
        from ami.tests.fixtures.tracking import pgvector_is_available

        detections = list(self.occurrences[0].detections.order_by("source_image__timestamp"))
        detections[0].next_detection = detections[1]
        detections[0].save(update_fields=["next_detection"])
        if pgvector_is_available():
            detections[0].classifications.update(features_2048=[0.1] * 2048)

        rows = {int(row["detection_id"]): row for row in self._rows()}
        self.assertEqual(rows[detections[0].pk]["next_detection_id"], str(detections[1].pk))
        self.assertEqual(rows[detections[1].pk]["next_detection_id"], "")
        self.assertEqual(rows[detections[1].pk]["has_feature_vector"], "false")
        if pgvector_is_available():
            self.assertEqual(rows[detections[0].pk]["has_feature_vector"], "true")

    def test_query_count_is_one_pair_per_chunk(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from ami.main.tests import cachalot_disabled

        # Three occurrences in chunks of two: occurrences, detections, occurrences, detections.
        with cachalot_disabled(), CaptureQueriesContext(connection) as ctx:
            rows = self._rows(chunk_size=2)
        self.assertEqual(len(rows), 9)
        self.assertEqual(len(ctx.captured_queries), 4)

        # Doubling the detections per occurrence adds no queries.
        for occurrence in self.occurrences:
            for detection in list(occurrence.detections.all()):
                detection.pk = None
                detection.next_detection = None
                detection.save()
        with cachalot_disabled(), CaptureQueriesContext(connection) as ctx:
            rows = self._rows(chunk_size=2)
        self.assertEqual(len(rows), 18)
        self.assertEqual(len(ctx.captured_queries), 4)

    def _run_command(self, **options) -> tuple[list[dict[str, str]], str]:
        import io

        from django.core.management import call_command

        stdout, stderr = io.StringIO(), io.StringIO()
        call_command("export_tracks", project=self.project.pk, stdout=stdout, stderr=stderr, **options)
        lines = stdout.getvalue().splitlines()
        self.assertEqual(lines[0], self.EXPECTED_HEADER)
        return list(csv.DictReader(lines)), stderr.getvalue()

    def test_management_command_writes_the_same_csv(self):
        rows, summary = self._run_command()
        self.assertEqual(len(rows), 9)
        self.assertIn("Wrote 9 detection rows", summary)

    def test_management_command_event_filter(self):
        import datetime

        from ami.main.models import Event

        first_event = self.captures[0].event
        other_event = Event.objects.create(
            project=self.project,
            deployment=self.deployment,
            group_by="2030-01-01",
            start=datetime.datetime(2030, 1, 1, 22, 0),
        )
        moved = self.occurrences[2]
        moved.event = other_event
        moved.save(update_fields=["event"])

        rows, _ = self._run_command(events=[first_event.pk])
        self.assertEqual(
            {row["occurrence_id"] for row in rows}, {str(self.occurrences[0].pk), str(self.occurrences[1].pk)}
        )
        self.assertEqual(len(rows), 6)

        rows, _ = self._run_command(events=[first_event.pk, other_event.pk])
        self.assertEqual({row["occurrence_id"] for row in rows}, {str(o.pk) for o in self.occurrences})
        self.assertEqual(len(rows), 9)

    def test_management_command_verified_only(self):
        from django.utils import timezone

        rows, _ = self._run_command(verified_only=True)
        self.assertEqual(rows, [], "No confirmed tracks yet, so only the header comes out")

        verified = self.occurrences[1]
        verified.grouping_verified_at = timezone.now()
        verified.save(update_fields=["grouping_verified_at"])
        rows, _ = self._run_command(verified_only=True)
        self.assertEqual({row["occurrence_id"] for row in rows}, {str(verified.pk)})
        self.assertEqual(len(rows), 3)
        self.assertEqual({row["grouping_verified"] for row in rows}, {"true"})

    def test_occurrence_csv_carries_grouping_confirmation(self):
        from django.utils import timezone

        verified = self.occurrences[0]
        verified.grouping_verified_at = timezone.now()
        verified.save(update_fields=["grouping_verified_at"])
        data_export = DataExport.objects.create(user=self.user, project=self.project, format="occurrences_simple_csv")
        file_path = data_export.run_export().replace("/media/", "")
        with default_storage.open(file_path, "r") as f:
            rows = {row["id"]: row for row in csv.DictReader(f)}
        default_storage.delete(file_path)
        self.assertNotIn("grouping_verified_by", next(iter(rows.values())))
        self.assertEqual(rows[str(verified.pk)]["grouping_verified"], "True")
        self.assertTrue(rows[str(verified.pk)]["grouping_verified_at"])
        self.assertEqual(rows[str(self.occurrences[1].pk)]["grouping_verified"], "False")
        self.assertEqual(rows[str(self.occurrences[1].pk)]["grouping_verified_at"], "")
