"""Tests for the storage source model, its consumers, and its API."""

import uuid
from urllib.parse import parse_qs, urlparse

from django.template.defaultfilters import filesizeformat
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from ami.main.models import Deployment, Project, SourceImage
from ami.main.models_future.storage import S3StorageSource
from ami.tests.fixtures.storage import S3_TEST_CONFIG, create_storage_source
from ami.users.models import User
from ami.users.roles import BasicMember, ProjectManager, create_roles_for_project
from ami.utils import s3


class TestStorageSourceConsumers(TestCase):
    """Deployment and SourceImage helpers that read from the deployment's storage source."""

    def setUp(self):
        short_id = uuid.uuid4().hex[:8]
        self.project = Project.objects.create(name=f"Storage Consumer Project {short_id}")
        self.source = S3StorageSource.objects.create(
            name=f"Consumer Source {short_id}",
            project=self.project,
            bucket="test-bucket",
            prefix="test_prefix",
            access_key="fake-access-key",
            secret_key="fake-secret-key",
            endpoint_url="http://minio:9000",
            public_base_url="http://minio:9000/test-bucket/test_prefix/",
        )
        self.deployment = Deployment.objects.create(
            name=f"Consumer Station {short_id}", project=self.project, data_source=self.source
        )

    def _create_capture(self, path: str = "20230601120000-snapshot.jpg") -> SourceImage:
        return SourceImage.objects.create(deployment=self.deployment, project=self.project, path=path)

    def test_data_source_uri_includes_subdir_and_regex(self):
        Deployment.objects.filter(pk=self.deployment.pk).update(
            data_source_subdir="/station_1/", data_source_regex=r".*\.jpg"
        )
        self.deployment.refresh_from_db()
        self.assertEqual(
            self.deployment.data_source_uri(),
            r"s3://test-bucket/test_prefix/station_1/?regex=.*\.jpg",
        )

    def test_data_source_uri_without_subdir_or_regex(self):
        self.assertEqual(self.deployment.data_source_uri(), "s3://test-bucket/test_prefix")

    def test_data_source_uri_is_none_without_a_storage_source(self):
        deployment = Deployment.objects.create(name="Unconnected Station", project=self.project)
        self.assertIsNone(deployment.data_source_uri())

    def test_data_source_total_size_display_without_an_indexed_size(self):
        self.assertIsNone(self.deployment.data_source_total_size)
        self.assertEqual(self.deployment.data_source_total_size_display(), filesizeformat(0))

    def test_capture_caches_the_base_url_from_the_storage_source(self):
        capture = self._create_capture()
        self.assertEqual(capture.get_base_url(), self.source.public_base_url)
        self.assertEqual(capture.public_base_url, self.source.public_base_url)
        self.assertEqual(
            capture.public_url(),
            "http://minio:9000/test-bucket/test_prefix/20230601120000-snapshot.jpg",
        )

    def test_capture_base_url_is_none_when_the_storage_source_has_no_public_url(self):
        self.source.public_base_url = None
        self.source.save()
        capture = self._create_capture()
        self.assertIsNone(capture.get_base_url())
        self.assertIsNone(capture.public_base_url)

    def test_capture_public_url_is_signed_when_the_storage_source_has_no_public_url(self):
        """With keys but no public base URL, every capture URL is presigned."""
        self.source.public_base_url = None
        self.source.save()
        capture = self._create_capture()

        url = capture.public_url()

        assert url is not None
        parsed_url = urlparse(url)
        self.assertEqual(parsed_url.netloc, "minio:9000")
        self.assertTrue(parsed_url.path.endswith(capture.path))
        self.assertIn("X-Amz-Signature", parse_qs(parsed_url.query))

    def test_capture_public_url_is_none_without_a_storage_source(self):
        deployment = Deployment.objects.create(name="Unconnected Station", project=self.project)
        capture = SourceImage.objects.create(
            deployment=deployment, project=self.project, path="20230601120000-snapshot.jpg"
        )
        self.assertIsNone(capture.public_url())
        with self.assertRaises(ValueError):
            capture.public_url(raise_errors=True)


class TestStorageSourceAPI(APITestCase):
    """Project scoping, write-only secrets, and the connection-test action."""

    def setUp(self):
        self.short_id = uuid.uuid4().hex[:8]
        self.project = Project.objects.create(name=f"Storage API Project {self.short_id}")
        self.other_project = Project.objects.create(name=f"Other Storage API Project {self.short_id}")
        create_roles_for_project(self.project)
        create_roles_for_project(self.other_project)

        self.manager = User.objects.create_user(
            email=f"pm-storage-{self.short_id}@insectai.org", password="password123"
        )
        ProjectManager.assign_user(self.manager, self.project)
        self.member = User.objects.create_user(
            email=f"member-storage-{self.short_id}@insectai.org", password="password123"
        )
        BasicMember.assign_user(self.member, self.project)
        self.outsider = User.objects.create_user(
            email=f"outsider-storage-{self.short_id}@insectai.org", password="password123"
        )

        self.source = create_storage_source(self.project, f"API Source {self.short_id}")
        self.other_source = create_storage_source(self.other_project, f"Other API Source {self.short_id}")

    def _test_url(self, source: S3StorageSource) -> str:
        return f"/api/v2/storage/{source.pk}/test/"

    def test_list_is_scoped_to_the_requested_project(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(f"/api/v2/storage/?project_id={self.project.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {row["id"] for row in response.json()["results"]}
        self.assertEqual(returned_ids, {self.source.pk}, "Only the active project's storage should be listed")

    def test_secrets_are_never_returned(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(f"/api/v2/storage/{self.source.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("access_key", response.json())
        self.assertNotIn("secret_key", response.json())

    def test_create_stores_secrets_without_echoing_them(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            "/api/v2/storage/",
            {
                "name": "Created Source",
                "project": self.project.pk,
                "bucket": "test-bucket",
                "access_key": "new-access-key",
                "secret_key": "new-secret-key",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("secret_key", response.json())

        created = S3StorageSource.objects.get(pk=response.json()["id"])
        self.assertEqual(created.access_key, "new-access-key")
        self.assertEqual(created.secret_key, "new-secret-key")

    def test_connection_test_reports_success(self):
        s3.write_random_file(self.source.config)
        self.client.force_authenticate(self.manager)

        response = self.client.post(self._test_url(self.source), {})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["connection_successful"])
        self.assertTrue(data["prefix_exists"])
        self.assertIsNotNone(data["first_file_found"])

    def test_connection_test_reports_an_empty_subdir_without_failing(self):
        self.client.force_authenticate(self.manager)

        response = self.client.post(self._test_url(self.source), {"subdir": f"missing_subdir_{self.short_id}"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["connection_successful"])
        self.assertFalse(data["prefix_exists"])
        self.assertEqual(data["files_checked"], 0)

    def test_connection_test_returns_400_for_a_missing_bucket(self):
        bad_source = S3StorageSource.objects.create(
            name="Missing Bucket Source",
            project=self.project,
            bucket=f"missing-bucket-{self.short_id}",
            endpoint_url=S3_TEST_CONFIG.endpoint_url,
            access_key=S3_TEST_CONFIG.access_key_id,
            secret_key=S3_TEST_CONFIG.secret_access_key,
        )
        self.client.force_authenticate(self.manager)

        response = self.client.post(self._test_url(bad_source), {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertEqual(data["code"], "NoSuchBucket")
        self.assertTrue(data["detail"])

    def test_connection_test_requires_the_test_permission(self):
        """``test`` maps to the ``test_s3storagesource`` project permission."""
        for user, label in [(self.member, "basic member"), (self.outsider, "non-member")]:
            with self.subTest(user=label):
                self.client.force_authenticate(user)
                response = self.client.post(self._test_url(self.source), {})
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_connection_test_is_denied_for_another_projects_source(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(self._test_url(self.other_source), {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_connection_test_is_denied_for_anonymous_users(self):
        response = self.client.post(self._test_url(self.source), {})
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
