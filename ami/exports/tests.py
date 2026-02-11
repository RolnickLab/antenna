import csv
import json
import logging
import zipfile
from io import StringIO
from xml.etree import ElementTree as ET

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase
from rest_framework.test import APIClient

from ami.exports.models import DataExport
from ami.main.models import Occurrence, SourceImageCollection
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


class DwCAExportTest(TestCase):
    """Tests for Darwin Core Archive (DwC-A) export format.

    Uses setUpClass to run the export once and share the ZIP across
    structural validation tests for better performance.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project, cls.deployment = setup_test_project(reuse=False)
        cls.user = cls.project.owner
        create_captures(deployment=cls.deployment, num_nights=2, images_per_night=4, interval_minutes=1)
        group_images_into_events(cls.deployment)
        create_taxa(cls.project)
        create_occurrences(num=10, deployment=cls.deployment)

        # Run the export once and cache the file path
        cls._export_file_path = cls._create_export(cls.project, cls.user)

    @classmethod
    def tearDownClass(cls):
        if cls._export_file_path and default_storage.exists(cls._export_file_path):
            default_storage.delete(cls._export_file_path)
        super().tearDownClass()

    @staticmethod
    def _create_export(project, user):
        """Run a DwC-A export and return the storage file path."""
        from django.conf import settings

        data_export = DataExport.objects.create(
            user=user,
            project=project,
            format="dwca",
            job=None,
        )
        file_url = data_export.run_export()
        assert file_url is not None, "Export did not produce a file URL"
        file_path = file_url.replace(settings.MEDIA_URL, "")
        assert default_storage.exists(file_path), f"Export file not found: {file_path}"
        return file_path

    def _open_zip(self):
        """Open the cached export ZIP for reading."""
        return default_storage.open(self._export_file_path, "rb")

    def test_dwca_exporter_is_registered(self):
        """DwC-A exporter should be registered and retrievable."""
        from ami.exports.registry import ExportRegistry

        exporter_cls = ExportRegistry.get_exporter("dwca")
        self.assertIsNotNone(exporter_cls, "DwC-A exporter not found in registry")
        self.assertEqual(exporter_cls.file_format, "zip")

    def test_export_produces_valid_zip(self):
        """Export should produce a valid ZIP with expected files."""
        with self._open_zip() as f:
            self.assertTrue(zipfile.is_zipfile(f))
            f.seek(0)
            with zipfile.ZipFile(f, "r") as zf:
                names = zf.namelist()
                self.assertIn("event.txt", names)
                self.assertIn("occurrence.txt", names)
                self.assertIn("meta.xml", names)
                self.assertIn("eml.xml", names)

    def test_event_headers_and_row_count(self):
        """event.txt should have correct headers and row count matching events."""
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                event_data = zf.read("event.txt").decode("utf-8")
                reader = csv.DictReader(StringIO(event_data), delimiter="\t")
                rows = list(reader)

                # Check headers
                self.assertIn("eventID", reader.fieldnames)
                self.assertIn("eventDate", reader.fieldnames)
                self.assertIn("decimalLatitude", reader.fieldnames)
                self.assertIn("samplingProtocol", reader.fieldnames)

                # Row count should match project events
                expected_count = self.project.events.count()
                self.assertEqual(len(rows), expected_count, "Event row count mismatch")

    def test_occurrence_headers_and_row_count(self):
        """occurrence.txt should have correct headers and row count matching valid occurrences."""
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                occ_data = zf.read("occurrence.txt").decode("utf-8")
                reader = csv.DictReader(StringIO(occ_data), delimiter="\t")
                rows = list(reader)

                # Check headers
                self.assertIn("occurrenceID", reader.fieldnames)
                self.assertIn("scientificName", reader.fieldnames)
                self.assertIn("basisOfRecord", reader.fieldnames)
                self.assertIn("taxonRank", reader.fieldnames)

                # Row count should match valid occurrences with event and determination
                expected_count = (
                    Occurrence.objects.valid()  # type: ignore[union-attr]
                    .filter(project=self.project, event__isnull=False, determination__isnull=False)
                    .count()
                )
                self.assertEqual(len(rows), expected_count, "Occurrence row count mismatch")

                # All rows should have basisOfRecord = MachineObservation
                for row in rows:
                    self.assertEqual(row["basisOfRecord"], "MachineObservation")

    def test_meta_xml_structure(self):
        """meta.xml should be valid XML with correct core/extension structure."""
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                meta_xml = zf.read("meta.xml").decode("utf-8")
                root = ET.fromstring(meta_xml)

                # Default namespace
                ns = "http://rs.tdwg.org/dwc/text/"

                # Should have a core element with Event rowType
                core = root.find(f"{{{ns}}}core")
                self.assertIsNotNone(core, "meta.xml missing <core> element")
                self.assertIn("Event", core.get("rowType", ""))

                # Should have an extension element with Occurrence rowType
                ext = root.find(f"{{{ns}}}extension")
                self.assertIsNotNone(ext, "meta.xml missing <extension> element")
                self.assertIn("Occurrence", ext.get("rowType", ""))

                # Core should reference event.txt
                core_location = core.find(f".//{{{ns}}}location")
                self.assertIsNotNone(core_location, "meta.xml core missing <location>")
                self.assertEqual(core_location.text, "event.txt")

                # Extension should reference occurrence.txt
                ext_location = ext.find(f".//{{{ns}}}location")
                self.assertIsNotNone(ext_location, "meta.xml extension missing <location>")
                self.assertEqual(ext_location.text, "occurrence.txt")

    def test_referential_integrity(self):
        """All occurrence eventIDs should reference existing event eventIDs."""
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                # Read event IDs
                event_data = zf.read("event.txt").decode("utf-8")
                event_reader = csv.DictReader(StringIO(event_data), delimiter="\t")
                event_ids = {row["eventID"] for row in event_reader}

                # Read occurrence eventIDs
                occ_data = zf.read("occurrence.txt").decode("utf-8")
                occ_reader = csv.DictReader(StringIO(occ_data), delimiter="\t")
                occ_event_ids = {row["eventID"] for row in occ_reader if row["eventID"]}

                # All occurrence eventIDs should exist in events
                orphaned = occ_event_ids - event_ids
                self.assertEqual(
                    len(orphaned),
                    0,
                    f"Orphaned occurrence eventIDs (not in events): {orphaned}",
                )

    def test_taxonomy_hierarchy_extraction(self):
        """Taxonomy fields should be extracted from parents_json."""
        from ami.exports.dwca import _get_rank_from_parents

        # Get an occurrence with a determination that has parents
        occurrence = (
            Occurrence.objects.valid()  # type: ignore[union-attr]
            .filter(project=self.project, determination__isnull=False)
            .select_related("determination")
            .first()
        )
        self.assertIsNotNone(occurrence, "No occurrence with determination found")

        # Update parents_json on the taxon so we can test extraction
        taxon = occurrence.determination
        taxon.save(update_calculated_fields=True)
        taxon.refresh_from_db()

        # Ensure parents_json is populated so this test doesn't pass vacuously
        self.assertTrue(taxon.parents_json, "Test taxon should have parents_json populated")

        ranks_found = []
        for rank in ["KINGDOM", "PHYLUM", "CLASS", "ORDER", "FAMILY", "GENUS"]:
            value = _get_rank_from_parents(occurrence, rank)
            if value:
                ranks_found.append(rank)
        self.assertGreater(len(ranks_found), 0, "No taxonomy ranks extracted from parents_json")

    def test_specific_epithet_extraction(self):
        """get_specific_epithet should extract the second word of a binomial name."""
        from ami.exports.dwca import get_specific_epithet

        self.assertEqual(get_specific_epithet("Vanessa cardui"), "cardui")
        self.assertEqual(get_specific_epithet("Vanessa"), "")
        self.assertEqual(get_specific_epithet(""), "")
        self.assertEqual(get_specific_epithet("Homo sapiens sapiens"), "sapiens")

    def test_eml_xml_valid(self):
        """eml.xml should be valid XML with project metadata."""
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                eml_xml = zf.read("eml.xml").decode("utf-8")
                root = ET.fromstring(eml_xml)

                # Should have a dataset element
                ns = {"eml": "eml://ecoinformatics.org/eml-2.1.1"}
                dataset = root.find("eml:dataset", ns) or root.find("dataset")
                self.assertIsNotNone(dataset, "eml.xml missing <dataset> element")

                # Title should match project name
                title = dataset.find("eml:title", ns) or dataset.find("title")
                self.assertIsNotNone(title)
                self.assertEqual(title.text, self.project.name)
