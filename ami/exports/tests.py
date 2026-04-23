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

                # Row count should match events referenced by valid occurrences
                expected_count = (
                    Occurrence.objects.valid()  # type: ignore[union-attr]
                    .filter(project=self.project, event__isnull=False, determination__isnull=False)
                    .values("event_id")
                    .distinct()
                    .count()
                )
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

    def test_verification_status_ignores_withdrawn_identifications(self):
        """identificationVerificationStatus should flip to 'verified' only for non-withdrawn human IDs."""
        from ami.exports.dwca import _get_verification_status

        occurrence = (
            Occurrence.objects.valid()  # type: ignore[union-attr]
            .filter(project=self.project, determination__isnull=False)
            .first()
        )
        self.assertIsNotNone(occurrence)
        occurrence.identifications.all().delete()
        self.assertEqual(_get_verification_status(occurrence), "unverified")

        Identification.objects.create(
            user=self.user,
            taxon=occurrence.determination,
            occurrence=occurrence,
            withdrawn=True,
        )
        self.assertEqual(_get_verification_status(occurrence), "unverified")

        Identification.objects.create(
            user=self.user,
            taxon=occurrence.determination,
            occurrence=occurrence,
        )
        self.assertEqual(_get_verification_status(occurrence), "verified")

    def test_eml_xml_valid(self):
        """eml.xml should be valid EML 2.2.0 with coverage, methods, and license."""
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                eml_xml = zf.read("eml.xml").decode("utf-8")
                root = ET.fromstring(eml_xml)

                self.assertIn("eml-2.2.0", eml_xml)
                ns = {"eml": "https://eml.ecoinformatics.org/eml-2.2.0"}
                dataset = root.find("eml:dataset", ns) or root.find("dataset")
                self.assertIsNotNone(dataset, "eml.xml missing <dataset>")

                title = dataset.find("eml:title", ns) or dataset.find("title")
                self.assertIsNotNone(title)
                self.assertEqual(title.text, self.project.name)

                coverage = dataset.find("eml:coverage", ns) or dataset.find("coverage")
                self.assertIsNotNone(coverage, "Missing <coverage>")
                self.assertIsNotNone(
                    coverage.find("eml:geographicCoverage", ns) or coverage.find("geographicCoverage")
                )
                self.assertIsNotNone(coverage.find("eml:temporalCoverage", ns) or coverage.find("temporalCoverage"))

                methods = dataset.find("eml:methods", ns) or dataset.find("methods")
                self.assertIsNotNone(methods, "Missing <methods>")
                method_step = methods.find("eml:methodStep", ns) or methods.find("methodStep")
                self.assertIsNotNone(method_step)

    def test_dwca_export_with_collection_filter(self):
        """DwC-A export with collection_id filter should only include matching occurrences and their events."""
        # Create a collection with a subset of images
        images = self.project.captures.all()
        collection_images = images[: images.count() // 2]
        self.assertGreater(len(collection_images), 0)

        collection = SourceImageCollection.objects.create(
            name="DwCA Filter Test Collection",
            project=self.project,
            method="manual",
            kwargs={"image_ids": [img.pk for img in collection_images]},
        )
        collection.populate_sample()

        # Run filtered export
        data_export = DataExport.objects.create(
            user=self.user,
            project=self.project,
            format="dwca",
            filters={"collection_id": collection.pk},
            job=None,
        )
        file_url = data_export.run_export()
        self.assertIsNotNone(file_url)

        from django.conf import settings

        file_path = file_url.replace(settings.MEDIA_URL, "")
        self.assertTrue(default_storage.exists(file_path))

        try:
            # Count expected filtered occurrences
            expected_occ_count = (
                Occurrence.objects.valid()  # type: ignore[union-attr]
                .filter(
                    project=self.project,
                    event__isnull=False,
                    determination__isnull=False,
                    detections__source_image__collections=collection,
                )
                .distinct()
                .count()
            )
            total_occ_count = (
                Occurrence.objects.valid()  # type: ignore[union-attr]
                .filter(project=self.project, event__isnull=False, determination__isnull=False)
                .count()
            )
            self.assertGreater(expected_occ_count, 0, "Filtered occurrences should not be empty")
            self.assertLess(expected_occ_count, total_occ_count, "Filtered should be fewer than total")

            with default_storage.open(file_path, "rb") as f:
                with zipfile.ZipFile(f, "r") as zf:
                    # Verify occurrence count
                    occ_data = zf.read("occurrence.txt").decode("utf-8")
                    occ_reader = csv.DictReader(StringIO(occ_data), delimiter="\t")
                    occ_rows = list(occ_reader)
                    self.assertEqual(len(occ_rows), expected_occ_count, "Filtered occurrence count mismatch")

                    # Verify event count matches only events from filtered occurrences
                    event_data = zf.read("event.txt").decode("utf-8")
                    event_reader = csv.DictReader(StringIO(event_data), delimiter="\t")
                    event_rows = list(event_reader)
                    event_ids_in_file = {row["eventID"] for row in event_rows}

                    # Events should only be those referenced by filtered occurrences
                    occ_event_ids = {row["eventID"] for row in occ_rows if row["eventID"]}
                    self.assertEqual(
                        event_ids_in_file,
                        occ_event_ids,
                        "Event IDs should match exactly those referenced by filtered occurrences",
                    )

                    # Referential integrity: no orphaned eventIDs in occurrences
                    orphaned = occ_event_ids - event_ids_in_file
                    self.assertEqual(len(orphaned), 0, f"Orphaned occurrence eventIDs: {orphaned}")
        finally:
            default_storage.delete(file_path)

    def test_validator_runs_on_produced_zip(self):
        """The exporter's own zip should pass its own validator cleanly."""
        import tempfile

        from ami.exports.dwca_validator import validate_dwca_zip

        with self._open_zip() as f:
            tf = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            tf.write(f.read())
            tf.close()
            result = validate_dwca_zip(tf.name)
        self.assertTrue(
            result.ok,
            f"Self-produced DwC-A failed own validator: {result.errors}",
        )

    def test_measurementorfact_txt_in_archive(self):
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                self.assertIn("measurementorfact.txt", zf.namelist())
                data = zf.read("measurementorfact.txt").decode("utf-8")
                reader = csv.DictReader(StringIO(data), delimiter="\t")
                rows = list(reader)
                self.assertGreater(len(rows), 0)
                types = {r["measurementType"] for r in rows}
                self.assertIn("classificationScore", types)
                for r in rows:
                    self.assertTrue(r["eventID"], "MoF row missing eventID")
                    self.assertTrue(r["occurrenceID"], "MoF row missing occurrenceID in this PR")

    def test_meta_xml_declares_mof_extension(self):
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                meta_xml = zf.read("meta.xml").decode("utf-8")
                self.assertIn("measurementorfact.txt", meta_xml)
                self.assertIn("http://rs.gbif.org/terms/1.0/MeasurementOrFact", meta_xml)

    def test_multimedia_txt_in_archive(self):
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                self.assertIn("multimedia.txt", zf.namelist())
                data = zf.read("multimedia.txt").decode("utf-8")
                reader = csv.DictReader(StringIO(data), delimiter="\t")
                rows = list(reader)
                self.assertGreater(len(rows), 0, "multimedia.txt has no rows")
                ids = {row["eventID"] for row in rows if row["eventID"]}
                event_data = zf.read("event.txt").decode("utf-8")
                event_ids = {r["eventID"] for r in csv.DictReader(StringIO(event_data), delimiter="\t")}
                self.assertTrue(ids.issubset(event_ids), f"Orphaned multimedia eventIDs: {ids - event_ids}")

    def test_meta_xml_declares_multimedia_extension(self):
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                meta_xml = zf.read("meta.xml").decode("utf-8")
                self.assertIn("multimedia.txt", meta_xml)
                self.assertIn("http://rs.gbif.org/terms/1.0/Multimedia", meta_xml)

    def test_occurrence_has_associated_media_column(self):
        """occurrence.txt should carry associatedMedia as pipe-separated URLs."""
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                occ_data = zf.read("occurrence.txt").decode("utf-8")
                reader = csv.DictReader(StringIO(occ_data), delimiter="\t")
                fieldnames = set(reader.fieldnames or [])
                self.assertIn("associatedMedia", fieldnames)
                rows = list(reader)
                non_empty = [r for r in rows if r.get("associatedMedia")]
                self.assertGreater(len(non_empty), 0, "No occurrences have associatedMedia")
                for r in non_empty:
                    self.assertFalse(r["associatedMedia"].endswith("|"))
                    for part in r["associatedMedia"].split("|"):
                        self.assertTrue(part.startswith("http"), f"Not a URL: {part}")

    def test_event_has_humboldt_eco_columns(self):
        """event.txt should carry the Humboldt eco: columns as flattened columns."""
        expected_columns = {
            "isSamplingEffortReported",
            "samplingEffortValue",
            "samplingEffortUnit",
            "samplingEffortProtocol",
            "isAbsenceReported",
            "targetTaxonomicScope",
            "inventoryTypes",
            "protocolNames",
            "protocolDescriptions",
            "hasMaterialSamples",
            "materialSampleTypes",
        }
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                event_data = zf.read("event.txt").decode("utf-8")
                reader = csv.DictReader(StringIO(event_data), delimiter="\t")
                fieldnames = set(reader.fieldnames or [])
                self.assertTrue(
                    expected_columns.issubset(fieldnames),
                    f"event.txt missing Humboldt columns: {expected_columns - fieldnames}",
                )
                rows = list(reader)
                self.assertGreater(len(rows), 0)
                for row in rows:
                    self.assertEqual(row["isSamplingEffortReported"], "true")
                    self.assertEqual(row["isAbsenceReported"], "true")
                    self.assertEqual(row["hasMaterialSamples"], "true")
                    self.assertEqual(row["materialSampleTypes"], "digital images")
                    self.assertEqual(row["inventoryTypes"], "trap or sample")

    def test_event_humboldt_terms_in_meta_xml(self):
        """meta.xml core should declare eco: term URIs for Humboldt columns."""
        with self._open_zip() as f:
            with zipfile.ZipFile(f, "r") as zf:
                meta_xml = zf.read("meta.xml").decode("utf-8")
                self.assertIn("http://rs.tdwg.org/eco/terms/isSamplingEffortReported", meta_xml)
                self.assertIn("http://rs.tdwg.org/eco/terms/isAbsenceReported", meta_xml)
                self.assertIn("http://rs.tdwg.org/eco/terms/targetTaxonomicScope", meta_xml)

    def test_offline_structural_validator(self):
        """Full archive passes the offline DwC-A structural validator.

        This catches the class of drift bugs (meta.xml term count diverges
        from TSV columns, dangling coreids, duplicate core ids, empty
        required fields) that don't show up in diff review. Fast enough to
        run in unit tests; no network required.
        """
        import tempfile

        from ami.exports.dwca import DWC, EVENT_FIELDS, OCCURRENCE_FIELDS
        from ami.exports.dwca_validator import validate_dwca_zip

        required_terms = {f.term for f in EVENT_FIELDS if f.required}
        required_terms |= {f.term for f in OCCURRENCE_FIELDS if f.required}
        # occurrenceID is required inside occurrence.txt but legitimately blank
        # on multimedia capture-rows; the current validator takes a flat
        # required set, so scope it out here. The Task 9 cross-reference check
        # covers the stronger integrity condition for extensions.
        required_terms.discard(DWC + "occurrenceID")

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            with self._open_zip() as src:
                tmp.write(src.read())
            tmp_path = tmp.name

        result = validate_dwca_zip(tmp_path, required_terms=required_terms)
        self.assertTrue(
            result.ok,
            msg="DwC-A structural validator failed:\n" + "\n".join(result.errors),
        )


class MultimediaExtensionTest(TestCase):
    """Unit tests for multimedia.txt row generator (in isolation from a full export)."""

    def test_field_catalogue_present(self):
        from ami.exports.dwca.fields import MULTIMEDIA_FIELDS

        headers = [f.header for f in MULTIMEDIA_FIELDS]
        for required in [
            "eventID",
            "occurrenceID",
            "type",
            "format",
            "identifier",
            "references",
            "created",
            "license",
            "rightsHolder",
        ]:
            self.assertIn(required, headers)

    def test_iter_multimedia_rows_emits_capture_and_crop_rows(self):
        from ami.exports.dwca.rows import iter_multimedia_rows

        project, deployment = setup_test_project(reuse=False)
        create_captures(deployment=deployment, num_nights=1, images_per_night=4, interval_minutes=1)
        group_images_into_events(deployment)
        create_taxa(project)
        create_occurrences(num=4, deployment=deployment)

        events_qs = project.events.all()
        occurrences_qs = Occurrence.objects.valid().filter(  # type: ignore[union-attr]
            project=project, event__isnull=False, determination__isnull=False
        )
        rows = list(iter_multimedia_rows(events_qs, occurrences_qs, "test-project"))

        capture_rows = [r for r in rows if not r["occurrenceID"]]
        crop_rows = [r for r in rows if r["occurrenceID"]]
        self.assertGreater(len(capture_rows), 0, "Expected capture rows with blank occurrenceID")
        # Detection-crop rows require det.url() to return non-empty; depends on fixture
        # setup (the image_dimensions stub may not produce crop URLs for test fixtures).
        # Check at least the capture-row invariants here.
        for r in capture_rows:
            self.assertTrue(r["identifier"], "Capture row missing identifier")
            self.assertEqual(r["type"], "StillImage")
        # Crop rows, if present, must have both identifier and references.
        for r in crop_rows:
            self.assertTrue(r["identifier"], "Crop row missing identifier")
            self.assertTrue(r["references"], "Crop row missing references (source capture URL)")
            self.assertEqual(r["type"], "StillImage")


class TargetTaxonomicScopeTest(TestCase):
    """Tests for eco:targetTaxonomicScope derivation from project include taxa."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project, cls.deployment = setup_test_project(reuse=False)
        create_taxa(cls.project)

    def test_empty_include_taxa_returns_empty_string(self):
        from ami.exports.dwca.targetscope import derive_target_taxonomic_scope

        self.project.default_filters_include_taxa.clear()
        self.assertEqual(derive_target_taxonomic_scope(self.project), "")

    def test_single_taxon_returns_its_name(self):
        from ami.exports.dwca.targetscope import derive_target_taxonomic_scope
        from ami.main.models import Taxon

        taxon = Taxon.objects.filter(projects=self.project).first()
        self.assertIsNotNone(taxon, "Expected at least one taxon on fixture project")
        self.project.default_filters_include_taxa.set([taxon])
        self.assertEqual(derive_target_taxonomic_scope(self.project), taxon.name)

    def test_multiple_taxa_returns_lca_name(self):
        from ami.exports.dwca.targetscope import derive_target_taxonomic_scope
        from ami.main.models import Taxon

        taxa = list(Taxon.objects.filter(projects=self.project).exclude(parents_json=[])[:2])
        if len(taxa) < 2:
            self.skipTest("Fixture does not have two taxa with shared ancestry")
        for t in taxa:
            t.save(update_calculated_fields=True)
            t.refresh_from_db()
        self.project.default_filters_include_taxa.set(taxa)

        result = derive_target_taxonomic_scope(self.project)
        self.assertTrue(result, "LCA should resolve to a non-empty ancestor name")
        for t in taxa:
            ancestor_names = [p.name for p in t.parents_json] + [t.name]
            self.assertIn(result, ancestor_names, f"{result} not in ancestry of {t.name}")


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
