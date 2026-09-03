import csv
import datetime
import json
import logging

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase
from rest_framework.test import APIClient

from ami.exports.models import DataExport
from ami.exports.registry import ExportRegistry
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


class TaxaListExportTest(TestCase):
    """Tests for the `taxa_list_csv` export format."""

    def setUp(self):
        self.project, self.deployment = setup_test_project(reuse=False)
        self.user = self.project.owner
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        # Two nights so we can test cross-midnight time-of-night aggregations.
        create_captures(deployment=self.deployment, num_nights=2, images_per_night=4, interval_minutes=30)
        group_images_into_events(self.deployment)
        create_taxa(self.project)
        # Ensure the project does not score-filter our test occurrences.
        self.project.default_filters_score_threshold = 0.0
        self.project.save()
        # All other tests in this suite share these defaults; reset M2M filters.
        self.project.default_filters_include_taxa.clear()
        self.project.default_filters_exclude_taxa.clear()

        # Build hierarchy ancestors first; reuse if create_taxa already made them.
        kingdom, _ = Taxon.objects.get_or_create(name="Animalia", defaults={"rank": "KINGDOM"})
        family, _ = Taxon.objects.get_or_create(
            name="Nymphalidae",
            defaults={"rank": "FAMILY", "parent": kingdom},
        )
        if family.parent_id != kingdom.pk:
            family.parent = kingdom
            family.save()

        # Three distinct taxa with different external-ID populations. Names
        # chosen to not collide with the create_taxa() fixture set.
        self.taxon_with_ids = Taxon.objects.create(
            name="Aglais io",
            rank="SPECIES",
            parent=family,
            gbif_taxon_key=1898286,
            inat_taxon_id=48662,
            bold_taxon_bin="BOLD:AAA0001",
            fieldguide_id="vanessa-cardui",
            cover_image_url="https://example.com/vc.jpg",
        )
        self.taxon_with_ids.projects.add(self.project)

        self.taxon_no_ids = Taxon.objects.create(name="Polygonia c-album", rank="SPECIES")
        self.taxon_no_ids.projects.add(self.project)

        self.taxon_genus_only = Taxon.objects.create(name="Aglais", rank="GENUS")
        self.taxon_genus_only.projects.add(self.project)

        # parents_json is populated via the manager helper.
        Taxon.objects.update_all_parents()
        self.taxon_with_ids.refresh_from_db()

        self.collection = self._create_collection()

    def _create_collection(self):
        images = list(self.project.captures.all())
        # Half the images go in the collection.
        half = len(images) // 2
        collection_images = images[:half]
        collection = SourceImageCollection.objects.create(
            name="taxa-list-test-collection",
            project=self.project,
            method="manual",
            kwargs={"image_ids": [img.pk for img in collection_images]},
        )
        collection.save()
        collection.populate_sample()
        return collection

    def _make_occurrence(self, taxon, source_image, score, timestamp=None):
        """Create one Occurrence with one Detection at a known timestamp+score."""
        ts = timestamp or source_image.timestamp
        detection = Detection.objects.create(
            source_image=source_image,
            timestamp=ts,
            bbox=[0.1, 0.1, 0.2, 0.2],
            path=f"detections/test_{taxon.pk}_{source_image.pk}.jpg",
        )
        detection.classifications.create(taxon=taxon, score=score, timestamp=ts)
        occurrence = detection.associate_new_occurrence()
        return occurrence, detection

    def _run_export(self, extra_filters=None):
        filters = {"collection_id": self.collection.pk}
        if extra_filters:
            filters.update(extra_filters)
        data_export = DataExport.objects.create(
            user=self.user,
            project=self.project,
            format="taxa_list_csv",
            filters=filters,
            job=None,
        )
        file_url = data_export.run_export()
        self.assertIsNotNone(file_url)
        file_path = file_url.replace("/media/", "")
        with default_storage.open(file_path, "r") as f:
            rows = list(csv.DictReader(f))
        default_storage.delete(file_path)
        return rows, data_export

    def test_smoke_collection_filter_and_filename_label(self):
        """End-to-end smoke: format is registered, the export writes a file
        scoped to the selected collection, and the filename carries the
        `taxa_list` label so it's distinguishable from occurrence exports."""
        self.assertIn("taxa_list_csv", ExportRegistry.get_supported_formats())

        in_capture = self.collection.images.first()
        self._make_occurrence(self.taxon_with_ids, in_capture, score=0.9)
        # Occurrence outside the collection — must not appear in output.
        all_images = list(self.project.captures.all())
        out_image = next(img for img in all_images if img.pk not in {c.pk for c in self.collection.images.all()})
        self._make_occurrence(self.taxon_no_ids, out_image, score=0.9)

        rows, data_export = self._run_export()
        names = {row["name"] for row in rows}
        self.assertEqual(names, {self.taxon_with_ids.name})
        self.assertEqual(rows[0]["direct_occurrences_count"], "1")
        self.assertIn("taxa_list", data_export.file_url or "")

    def test_score_aggregations_and_default_threshold(self):
        """min/max/avg score across occurrences, and project default
        score-threshold filter wires through (low-score occurrences excluded)."""
        self.project.default_filters_score_threshold = 0.5
        self.project.save()

        captures = list(self.collection.images.all()[:4])
        self.assertGreaterEqual(len(captures), 4)
        # Three high-score occurrences for the same taxon — these survive.
        for cap, score in zip(captures[:3], [0.6, 0.8, 1.0]):
            self._make_occurrence(self.taxon_with_ids, cap, score=score)
        # One low-score occurrence for a different taxon — filtered out.
        self._make_occurrence(self.taxon_no_ids, captures[3], score=0.1)

        rows, _ = self._run_export()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["name"], self.taxon_with_ids.name)
        self.assertEqual(row["direct_occurrences_count"], "3")
        self.assertAlmostEqual(float(row["min_score"]), 0.6, places=4)
        self.assertAlmostEqual(float(row["max_score"]), 1.0, places=4)
        self.assertAlmostEqual(float(row["avg_score"]), 0.8, places=4)

    def test_external_links_and_hierarchy_columns(self):
        """One row with full external IDs + hierarchy populated; one row with
        none, to confirm both shapes render correctly."""
        cap1, cap2 = list(self.collection.images.all())[:2]
        self._make_occurrence(self.taxon_with_ids, cap1, score=0.9)
        self._make_occurrence(self.taxon_no_ids, cap2, score=0.9)

        rows, _ = self._run_export()
        by_name = {row["name"]: row for row in rows}
        with_ids = by_name[self.taxon_with_ids.name]
        no_ids = by_name[self.taxon_no_ids.name]

        # External links populated.
        self.assertEqual(with_ids["gbif_url"], "https://www.gbif.org/species/1898286")
        self.assertEqual(with_ids["inat_url"], "https://www.inaturalist.org/taxa/48662")
        self.assertIn("BOLD:AAA0001", with_ids["bold_url"])
        self.assertEqual(with_ids["fieldguide_url"], "https://fieldguide.app/taxa/vanessa-cardui")
        self.assertEqual(with_ids["cover_image_url"], "https://example.com/vc.jpg")
        # Hierarchy columns populated from parents_json + own rank.
        self.assertEqual(with_ids["kingdom"], "Animalia")
        self.assertEqual(with_ids["family"], "Nymphalidae")
        self.assertEqual(with_ids["species"], "Aglais io")

        # No-ID taxon has blank link columns and no hierarchy ancestors.
        self.assertEqual(no_ids["gbif_url"], "")
        self.assertEqual(no_ids["inat_url"], "")
        self.assertEqual(no_ids["bold_url"], "")
        self.assertEqual(no_ids["fieldguide_url"], "")
        self.assertEqual(no_ids["kingdom"], "")
        self.assertEqual(no_ids["family"], "")

    def test_time_of_night_wraparound(self):
        """Avg of 22:00 and 02:00 should be ~00:00 (midnight), not 12:00 (noon).

        This is the only nontrivial aggregation in the format and the reason
        we shift to a noon-anchored axis before averaging.
        """
        captures = list(self.collection.images.all())
        self.assertGreaterEqual(len(captures), 2)

        base_date = datetime.date(2026, 5, 1)
        ts_evening = datetime.datetime.combine(base_date, datetime.time(22, 0, 0))
        ts_early_morning = datetime.datetime.combine(base_date + datetime.timedelta(days=1), datetime.time(2, 0, 0))

        self._make_occurrence(self.taxon_with_ids, captures[0], score=0.9, timestamp=ts_evening)
        self._make_occurrence(self.taxon_with_ids, captures[1], score=0.9, timestamp=ts_early_morning)

        rows, _ = self._run_export()
        row = next(r for r in rows if r["name"] == self.taxon_with_ids.name)
        # In noon-anchored space, 22:00 is the start of the night (10h after
        # noon) and 02:00 is the end (14h after noon).
        self.assertEqual(row["session_time_min"], "22:00:00")
        self.assertEqual(row["session_time_max"], "02:00:00")
        h, m, s = row["session_time_median"].split(":")
        median_seconds = int(h) * 3600 + int(m) * 60 + int(s)
        # Median of two values lands at the midnight midpoint; accept ±60s.
        self.assertTrue(
            median_seconds <= 60 or median_seconds >= 86340,
            f"session_time_median {row['session_time_median']} should be near 00:00",
        )


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
