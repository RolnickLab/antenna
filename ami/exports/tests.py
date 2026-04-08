import csv
import datetime
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
            timestamp=datetime.datetime.now(),
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
        self.assertEqual(row["verified_by_count"], "0")

    def test_ml_prediction_with_agreeing_human(self):
        """Human agrees with ML: verified_by set, determination_matches = True, determination_score = None."""
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
        self.assertEqual(row["verified_by_count"], "1")
        self.assertEqual(row["agreed_with_algorithm"], "test-classifier")
        self.assertEqual(row["determination_matches_machine_prediction"], "True")

        # determination_score should be empty/None for human-determined occurrences
        self.assertIn(row["determination_score"], ["", "None", None])

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

    def test_multiple_identifications_count(self):
        """Multiple identifications: verified_by_count reflects all non-withdrawn IDs."""
        occurrence, _ = self._create_occurrence_with_prediction()

        from ami.users.models import User

        user2 = User.objects.create_user(email="verifier2@test.org")

        Identification.objects.create(user=self.user, taxon=self.taxon_a, occurrence=occurrence)
        Identification.objects.create(user=user2, taxon=self.taxon_a, occurrence=occurrence)

        rows = self._run_csv_export()
        row = next(r for r in rows if int(r["id"]) == occurrence.pk)
        self.assertEqual(row["verified_by_count"], "2")

    def test_detection_bbox_field(self):
        """Best detection bbox is included in export."""
        occurrence, _ = self._create_occurrence_with_prediction()
        rows = self._run_csv_export()
        row = next(r for r in rows if int(r["id"]) == occurrence.pk)
        self.assertIn("best_detection_bbox", row)
        # bbox should be a string representation of the list
        self.assertIn("0.1", row["best_detection_bbox"])

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
            "verified_by_count",
            "agreed_with_algorithm",
            "determination_matches_machine_prediction",
            "best_detection_bbox",
            "best_detection_source_image_url",
            "best_detection_occurrence_url",
        ]
        for field in expected_fields:
            self.assertIn(field, headers, f"Missing CSV field: {field}")

    def test_occurrence_url_field(self):
        """best_detection_occurrence_url contains a valid platform link."""
        occurrence, _ = self._create_occurrence_with_prediction()
        rows = self._run_csv_export()
        row = next(r for r in rows if int(r["id"]) == occurrence.pk)
        url = row.get("best_detection_occurrence_url", "")
        if url:
            self.assertIn(str(occurrence.pk), url)
