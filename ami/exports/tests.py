import csv
import json

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
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        # Create captures & occurrences to test exporting
        create_captures(deployment=self.deployment, num_nights=2, images_per_night=4, interval_minutes=1)
        group_images_into_events(self.deployment)
        create_taxa(self.project)
        create_occurrences(num=10, deployment=self.deployment)
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
        images = self.deployment.captures.all()

        # Create the collection
        collection = SourceImageCollection.objects.create(
            name="Test Manual Source Image Collection",
            project=self.project,
            method="manual",
            kwargs={"image_ids": [image.pk for image in images]},
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
            elif format_type == "occurrences_simple_json":
                self.validate_json_records(f)

        # Clean up the exported file after the test
        default_storage.delete(file_path)

    def validate_csv_records(self, file):
        """Validate record count in CSV."""
        csv_reader = csv.DictReader(file)
        row_count = sum(1 for row in csv_reader)
        expected_count = Occurrence.objects.filter(detections__source_image__collections=self.collection).count()
        self.assertEqual(row_count, expected_count)

    def validate_json_records(self, file):
        """Validate record count in JSON."""
        data = json.load(file)
        expected_count = Occurrence.objects.filter(detections__source_image__collections=self.collection).count()
        self.assertEqual(len(data), expected_count)

    def test_csv_export_record_count(self):
        """Test CSV export record count."""
        self.run_and_validate_export("occurrences_simple_csv")

    def test_json_export_record_count(self):
        """Test JSON export record count."""
        self.run_and_validate_export("occurrences_simple_json")
