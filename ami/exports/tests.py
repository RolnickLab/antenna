import csv
import json
import logging
from unittest import mock

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase
from rest_framework.test import APIClient, APITestCase

from ami.exports.models import DataExport
from ami.jobs.models import Job
from ami.main.models import Detection, Identification, Occurrence, SourceImageCollection, Taxon
from ami.main.models_future.tests.test_occurrence_filters import (
    LIST_QUERIES,
    build_filter_fixture,
    saved_filters_from_query,
)
from ami.main.occurrence_filters import clean_saved_filters
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


class ExportFiltersTest(APITestCase):
    """An export selects the occurrences that the occurrence list shows for the same filters."""

    formats = ["occurrences_simple_csv", "occurrences_api_json"]

    @classmethod
    def setUpTestData(cls):
        cls.fx = build_filter_fixture()

    def setUp(self):
        self.client.force_authenticate(self.fx.user)

    def _list_labels(self, query: str) -> set[str]:
        response = self.client.get(f"/api/v2/occurrences/?project_id={self.fx.project.pk}&limit=100&{query}")
        self.assertEqual(response.status_code, 200, response.content)
        return {self.fx.labels[row["id"]] for row in response.json()["results"]}

    def _export_labels(self, data_export: DataExport) -> list[str]:
        return [self.fx.labels[pk] for pk in data_export.get_exporter().queryset.values_list("pk", flat=True)]

    def _create(self, filters):
        with mock.patch.object(Job, "enqueue"):
            return self.client.post(
                "/api/v2/exports/",
                {"project": self.fx.project.pk, "format": "occurrences_simple_csv", "filters": filters},
                format="json",
            )

    def test_export_selects_what_the_list_shows(self):
        for query, expected in LIST_QUERIES.items():
            if "verified_by_me" in query:
                continue
            filters = clean_saved_filters(saved_filters_from_query(self.fx.query(query)))
            for format_type in self.formats:
                with self.subTest(query=query, format=format_type):
                    data_export = DataExport.objects.create(
                        user=self.fx.user, project=self.fx.project, format=format_type, filters=filters
                    )
                    labels = self._export_labels(data_export)
                    self.assertEqual(len(labels), len(set(labels)), "an occurrence is exported twice")
                    self.assertEqual(set(labels), expected)

    def test_csv_export_file_holds_the_filtered_occurrences(self):
        query = self.fx.query("taxon={genus}&date_start={day_2}")
        response = self._create(saved_filters_from_query(query))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["record_count"], 2)

        # Run without the job the API queued, whose progress stages only exist once it starts.
        data_export = DataExport.objects.create(
            user=self.fx.user,
            project=self.fx.project,
            format="occurrences_simple_csv",
            filters=response.json()["filters"],
        )
        file_path = data_export.run_export().replace("/media/", "")
        with default_storage.open(file_path, "r") as f:
            exported = {self.fx.labels[int(row["id"])] for row in csv.DictReader(f)}
        default_storage.delete(file_path)
        self.assertEqual(exported, self._list_labels(query))
        self.assertEqual(exported, {"o3", "o6"})

    def test_create_stores_filters_in_normal_form(self):
        refs = self.fx.refs
        response = self._create({"collection": str(refs["capture_set_2"]), "date_start": refs["day_2"]})
        self.assertEqual(response.status_code, 201, response.content)
        data_export = DataExport.objects.get(pk=response.json()["id"])
        self.assertEqual(
            data_export.filters,
            {"collection_id": refs["capture_set_2"], "date_start": refs["day_2"], "apply_defaults": True},
        )
        self.assertEqual(
            data_export.filters_display["collection"],
            {"type": "capture_set", "id": refs["capture_set_2"], "name": "Filters capture set 2"},
        )
        self.assertEqual(data_export.job.source_image_collection_id, refs["capture_set_2"])

        response = self._create(None)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(DataExport.objects.get(pk=response.json()["id"]).filters, {"apply_defaults": True})

    def test_create_refuses_bad_filters_with_400(self):
        for filters, key in [
            ({"collection_id": "abc"}, "collection_id"),
            ({"date_start": "2024-02-01", "date_end": "2024-01-01"}, "date_start"),
            ({"taxon": 999999999}, "taxon"),
            ({"limit": 10}, "limit"),
            ({"verified_by_me": True}, "verified_by_me"),
        ]:
            with self.subTest(filters=filters):
                response = self._create(filters)
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn(key, response.json()["filters"])
        self.assertFalse(DataExport.objects.exists())

    def test_export_saved_before_validation_runs_as_before(self):
        """Such an export applied only its capture set filter, without the project's default filters."""
        refs = self.fx.refs
        filters = {"collection_id": str(refs["capture_set_2"]), "date_start": refs["day_1"], "verified": "true"}
        data_export = DataExport.objects.create(
            user=self.fx.user, project=self.fx.project, format="occurrences_simple_csv", filters=filters
        )
        expected = self._list_labels(f"collection_id={refs['capture_set_2']}&apply_defaults=false")
        self.assertEqual(expected, {"o3", "o4", "o6"})
        self.assertEqual(set(self._export_labels(data_export)), expected)
        data_export.update_record_count()
        data_export.refresh_from_db()
        self.assertEqual(data_export.filters, filters)
        self.assertEqual(data_export.record_count, 3)
