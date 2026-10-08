import logging
import uuid
from unittest import mock
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from django.template.defaultfilters import filesizeformat
from django.test import TestCase

import ami.tasks
from ami.main.models import Deployment, Project, S3StorageSource, SourceImage
from ami.tests.fixtures.main import create_captures, create_captures_from_files, setup_test_project
from ami.tests.fixtures.storage import S3_TEST_CONFIG
from ami.utils import s3

logger = logging.getLogger(__name__)


class TestS3(TestCase):
    def setUp(self):
        self.config = S3_TEST_CONFIG
        # self.config.bucket_name = f"s3_test_bucket_{self._testMethodName}"
        # self.config.bucket_name = f"s3_test_bucket_123"
        s3.create_bucket(self.config, self.config.bucket_name)

    def tearDown(self) -> None:
        bucket = s3.get_bucket(self.config)
        bucket.objects.all().delete()
        bucket.object_versions.delete()
        bucket.delete()

    def _test_connection_no_files(self):
        # This test is disabled because it fails when running all tests together.
        # @TODO Fix this test
        result = s3.test_connection(self.config)
        self.assertTrue(result.connection_successful)
        self.assertIsNone(result.first_file_found, f"Bucket should be empty but found {result.first_file_found}")
        self.assertFalse(result.prefix_exists)

    def test_connection_with_files(self):
        test_key, _test_val = s3.write_random_file(self.config, key_prefix="apple_")
        num_extra_files = 5
        for _ in range(num_extra_files):
            s3.write_random_file(self.config)
        result = s3.test_connection(self.config)
        self.assertTrue(result.connection_successful)
        self.assertIsNotNone(result.first_file_found)
        self.assertTrue(result.prefix_exists)
        self.assertEqual(result.files_checked, 1)
        first_file_path = str(urlparse(result.first_file_found).path)
        full_key_path = s3.make_full_key_uri(self.config, test_key, with_protocol=False)
        self.assertEqual(first_file_path, full_key_path)

    def test_list_files_with_blank_key(self):
        """
        For some reason, the list_files function returns nothing
        if there is a blank key (an object without a name).
        """
        for _ in range(5):
            s3.write_random_file(self.config)

        obj = s3.write_file(self.config, key="", body=b"")
        obj.wait_until_exists()

        result = s3.test_connection(self.config)
        self.assertTrue(result.connection_successful)

        issue_is_fixed = False

        if issue_is_fixed:
            self.assertEqual(result.files_checked, 1)
            self.assertIsNotNone(result.first_file_found)
            self.assertTrue(result.prefix_exists)

        else:
            self.assertEqual(result.files_checked, 0)
            self.assertIsNone(result.first_file_found)
            self.assertFalse(result.prefix_exists)

    def test_connection_with_subdir(self):
        deployment_subdir = "test_subdir"
        key_prefix = f"{deployment_subdir}/test"
        test_key, _test_val = s3.write_random_file(self.config, key_prefix=key_prefix)
        result = s3.test_connection(self.config)
        self.assertTrue(result.connection_successful)
        self.assertTrue(result.prefix_exists)
        self.assertEqual(result.files_checked, 1)
        self.assertIsNotNone(result.first_file_found)
        first_file_path = str(urlparse(result.first_file_found).path)
        full_key_path = s3.make_full_key_uri(self.config, test_key, with_protocol=False)
        self.assertEqual(first_file_path, full_key_path)

    def test_connection_with_subdir_no_match(self):
        s3.write_random_file(self.config)
        result = s3.test_connection(self.config, subdir="random_subdir_3534353564")
        self.assertTrue(result.connection_successful)
        self.assertIsNone(result.first_file_found)
        self.assertFalse(result.prefix_exists)
        self.assertEqual(result.files_checked, 0)

    def test_connection_with_files_regex(self):
        num_unmatched_files = 5
        for _ in range(num_unmatched_files):
            s3.write_random_file(self.config, key_prefix="apple_")
        test_key, test_val = s3.write_random_file(self.config, key_prefix="quack_")
        result = s3.test_connection(self.config, regex_filter="quack_")
        self.assertTrue(result.connection_successful)
        self.assertTrue(result.prefix_exists)
        self.assertIsNotNone(result.first_file_found)
        self.assertEqual(result.files_checked, num_unmatched_files + 1)
        first_file_path = str(urlparse(result.first_file_found).path)
        full_key_path = s3.make_full_key_uri(self.config, test_key, with_protocol=False)
        self.assertEqual(first_file_path, full_key_path)

    def test_connection_with_files_regex_no_match(self):
        num_unmatched_files = 5
        for _ in range(num_unmatched_files):
            s3.write_random_file(self.config, key_prefix="apple_")
        result = s3.test_connection(self.config, regex_filter="quack_")
        self.assertTrue(result.connection_successful)
        self.assertIsNone(result.first_file_found)
        self.assertEqual(result.files_checked, num_unmatched_files)

    def test_write_and_count(self):
        count = s3.count_files(self.config)
        test_key, test_val = s3.write_random_file(self.config)
        self.assertEqual(s3.count_files(self.config), count + 1)
        out_val = s3.read_file(self.config, test_key)
        self.assertEqual(test_val, out_val)

    def test_presigned_url(self):
        test_key, test_val = s3.write_random_file(self.config)
        url = s3.get_presigned_url(self.config, test_key)
        url_parts = urlparse(url)
        params = parse_qs(url_parts.query)

        # Test path is correct
        full_key_uri = s3.make_full_key_uri(self.config, test_key, with_protocol=False)
        self.assertEqual(url_parts.path, full_key_uri)
        self.assertIn("X-Amz-Credential", params)

        # Test that the URL is accessible (minio is a dependency of the app container and should be running)
        resp = requests.get(url)
        resp.raise_for_status()

        # Test that the content is correct
        out_val = resp.content
        self.assertEqual(test_val, out_val)


class TestS3PrefixUtils(TestCase):
    def setUp(self):
        self.config = s3.S3Config(
            endpoint_url="http://minio:9000",
            access_key_id="minioadmin",
            secret_access_key="minioadmin",
            bucket_name="test_bucket",
            prefix="test_prefix",
            public_base_url="http://minio:9000/test",
        )

    def test_key_with_prefix_no_subdir(self):
        key = "file.txt"
        result = s3.key_with_prefix(self.config, key)
        expected = "test_prefix/file.txt"
        self.assertEqual(result, expected)

    def test_key_with_prefix_with_subdir(self):
        key = "subdir/file.txt"
        result = s3.key_with_prefix(self.config, key, subdir="subdir")
        expected = "test_prefix/subdir/file.txt"
        self.assertEqual(result, expected)

    def test_key_with_prefix_with_leading_slash(self):
        key = "/file.txt"
        result = s3.key_with_prefix(self.config, key)
        expected = "test_prefix/file.txt"
        self.assertEqual(result, expected)

    def test_key_with_prefix_with_subdir_and_leading_slash(self):
        key = "/subdir/file.txt"
        result = s3.key_with_prefix(self.config, key, subdir="subdir")
        expected = "test_prefix/subdir/file.txt"
        self.assertEqual(result, expected)

    def test_key_full_uri_with_protocol(self):
        key = "subdir/file.txt"
        result = s3.make_full_key_uri(self.config, key, with_protocol=True)
        expected = "s3://test_bucket/test_prefix/subdir/file.txt"
        self.assertEqual(result, expected)

    def test_key_full_uri_without_protocol(self):
        key = "subdir/file.txt"
        result = s3.make_full_key_uri(self.config, key, with_protocol=False)
        expected = "/test_bucket/test_prefix/subdir/file.txt"
        self.assertEqual(result, expected)


class TestStorageSource(TestCase):
    def setUp(self):
        self.project, self.deployment = setup_test_project()
        self.captures = create_captures_from_files(self.deployment)
        self.storage_source: S3StorageSource | None = self.deployment.data_source
        self.assertIsNotNone(self.storage_source)

    def test_write_file(self):
        assert isinstance(self.storage_source, S3StorageSource)

        s3.write_random_file(self.storage_source.config)

    def test_private_url(self):
        assert isinstance(self.storage_source, S3StorageSource)

        # Ensure that the public base URL is not set so public_url() will return a signed URL
        self.storage_source.public_base_url = None
        self.storage_source.save()

        path, content = s3.write_random_file(self.storage_source.config)
        url = self.storage_source.public_url(path=path)

        # Check that the URL is correct:
        parsed_url = urlparse(url)
        self.assertEqual(parsed_url.scheme, "http")
        self.assertTrue(parsed_url.path.endswith(path))

        # Check that it contains params for the signature
        query = parse_qs(parsed_url.query)
        self.assertIn("X-Amz-Signature", query)
        self.assertIn("X-Amz-Algorithm", query)
        self.assertIn("X-Amz-Credential", query)
        self.assertIn("X-Amz-Date", query)
        self.assertIn("X-Amz-Expires", query)
        self.assertIn("X-Amz-SignedHeaders", query)

        # Try to access the URL
        response = requests.get(url)
        response.raise_for_status()
        self.assertTrue(response.ok)
        self.assertEqual(response.content, content)

    def _test_public_url(self):
        # @TODO Fix this. I can't get minio to make the test bucket public
        # This errors with "403 Client Error: Forbidden for url"
        assert isinstance(self.storage_source, S3StorageSource)
        # public_base_url = "http://minio:9000/ami-test/test_prefix"
        public_path = s3.join_path(self.storage_source.config.bucket_name, self.storage_source.config.prefix)
        assert self.storage_source.config.endpoint_url is not None
        public_base_url = urljoin(self.storage_source.config.endpoint_url, public_path)
        self.storage_source.public_base_url = public_base_url
        self.storage_source.save()

        path, content = s3.write_random_file(self.storage_source.config)
        url = self.storage_source.public_url(path=path)

        # Check that the URL is correct:
        parsed_url = urlparse(url)
        self.assertEqual(parsed_url.scheme, "http")
        self.assertTrue(parsed_url.path.endswith(path))

        # Try to access the URL
        response = requests.get(url)
        response.raise_for_status()
        self.assertTrue(response.ok)
        self.assertEqual(response.content, content)

    def test_connection(self):
        assert isinstance(self.storage_source, S3StorageSource)
        s3.write_random_file(self.storage_source.config)
        status = self.storage_source.test_connection()
        self.assertTrue(status.connection_successful)
        self.assertIsNotNone(status.first_file_found)

    def test_count_files_saves_the_total(self):
        assert isinstance(self.storage_source, S3StorageSource)

        count = self.storage_source.count_files()

        self.assertGreater(count, 0, "The test bucket was populated, so files should be counted")
        self.storage_source.refresh_from_db()
        self.assertEqual(self.storage_source.total_files, count)

    def test_calculate_size_saves_the_total_size_and_file_count(self):
        assert isinstance(self.storage_source, S3StorageSource)

        size = self.storage_source.calculate_size()

        self.assertGreater(size, 0)
        self.storage_source.refresh_from_db()
        self.assertEqual(self.storage_source.total_size, size)
        self.assertGreater(self.storage_source.total_files or 0, 0)

    def test_calculate_storage_size_task_saves_the_total(self):
        """The admin action and Celery both reach calculate_size() through this task."""
        assert isinstance(self.storage_source, S3StorageSource)

        size = ami.tasks.calculate_storage_size(self.storage_source.pk)

        self.storage_source.refresh_from_db()
        self.assertEqual(self.storage_source.total_size, size)

    def test_capture_dimensions_are_read_from_the_storage_source(self):
        """SourceImage.get_dimensions() reads the original image through the data source."""
        capture, frame = self.captures[0]
        # The sync already measured this capture; clear it so the read is unambiguous.
        SourceImage.objects.filter(pk=capture.pk).update(width=None, height=None)
        capture.refresh_from_db()

        width, height = capture.get_dimensions()

        self.assertEqual((width, height), (frame.width, frame.height))
        capture.refresh_from_db()
        self.assertEqual((capture.width, capture.height), (frame.width, frame.height))


class TestStorageSourceModel(TestCase):
    """``S3StorageSource`` logic that does not need a live object store."""

    def setUp(self):
        short_id = uuid.uuid4().hex[:8]
        self.project = Project.objects.create(name=f"Storage Model Project {short_id}")
        self.source = S3StorageSource.objects.create(
            name=f"Model Source {short_id}",
            project=self.project,
            bucket="test-bucket",
            prefix="test_prefix",
            region="us-east-1",
            access_key="fake-access-key",
            secret_key="fake-secret-key",
            endpoint_url="http://minio:9000",
            public_base_url="http://minio:9000/test-bucket/test_prefix/",
        )

    def _create_deployment(self, name: str, **indexed_totals) -> Deployment:
        """Create a station on this storage source with the given indexed totals.

        ``Deployment.save()`` recalculates ``data_source_total_*`` and ``captures_count``
        from the captures a station actually has, so the totals are written with a
        queryset update instead of being passed to ``create()``.
        """
        deployment = Deployment.objects.create(name=name, project=self.project, data_source=self.source)
        if indexed_totals:
            Deployment.objects.filter(pk=deployment.pk).update(**indexed_totals)
            deployment.refresh_from_db()
        return deployment

    def test_config_maps_connection_fields(self):
        config = self.source.config
        self.assertEqual(config.bucket_name, "test-bucket")
        self.assertEqual(config.prefix, "test_prefix")
        self.assertEqual(config.region, "us-east-1")
        self.assertEqual(config.access_key_id, "fake-access-key")
        self.assertEqual(config.secret_access_key, "fake-secret-key")
        self.assertEqual(config.endpoint_url, "http://minio:9000")
        self.assertEqual(config.public_base_url, "http://minio:9000/test-bucket/test_prefix/")

    def test_uri_joins_bucket_prefix_and_path(self):
        self.assertEqual(self.source.uri("subdir/file.jpg"), "s3://test-bucket/test_prefix/subdir/file.jpg")

    def test_uri_without_path_is_the_prefix_root(self):
        self.assertEqual(self.source.uri(), "s3://test-bucket/test_prefix")

    def test_uri_strips_surrounding_slashes(self):
        self.assertEqual(self.source.uri("/subdir/file.jpg/"), "s3://test-bucket/test_prefix/subdir/file.jpg")

    def test_uri_without_prefix_omits_the_empty_segment(self):
        source = S3StorageSource.objects.create(
            name="No Prefix Source", project=self.project, bucket="test-bucket", prefix=""
        )
        self.assertEqual(source.uri("file.jpg"), "s3://test-bucket/file.jpg")

    def test_indexed_totals_sum_across_deployments(self):
        self._create_deployment("One", data_source_total_files=10, data_source_total_size=1024, captures_count=10)
        self._create_deployment("Two", data_source_total_files=5, data_source_total_size=512, captures_count=4)

        source = S3StorageSource.objects.get(pk=self.source.pk)
        self.assertEqual(source.deployments_count(), 2)
        self.assertEqual(source.total_files_indexed(), 15)
        self.assertEqual(source.total_size_indexed(), 1536)
        self.assertEqual(source.total_captures_indexed(), 14)
        self.assertEqual(source.total_size_indexed_display(), filesizeformat(1536))

    def test_indexed_totals_with_no_deployments(self):
        """The storage API exposes these fields for sources not yet wired to a station."""
        self.assertEqual(self.source.deployments_count(), 0)
        self.assertIsNone(self.source.total_files_indexed())
        self.assertIsNone(self.source.total_size_indexed())
        self.assertIsNone(self.source.total_captures_indexed())
        # filesizeformat() swallows the None and reports zero rather than raising.
        self.assertEqual(self.source.total_size_indexed_display(), filesizeformat(0))

    def test_total_size_indexed_is_not_memoized(self):
        """A fresh instance of the same row must see newly indexed data.

        ``Model.__hash__`` is the pk, so a ``functools.cache`` on this method freezes
        the total for every instance of the row for the life of the process.
        """
        self._create_deployment("First", data_source_total_size=1024)
        self.assertEqual(S3StorageSource.objects.get(pk=self.source.pk).total_size_indexed(), 1024)

        self._create_deployment("Second", data_source_total_size=512)
        self.assertEqual(S3StorageSource.objects.get(pk=self.source.pk).total_size_indexed(), 1536)

    def test_changing_public_base_url_updates_capture_urls(self):
        """Captures cache the base URL, so changing it has to rewrite them."""
        deployment = self._create_deployment("Station With Captures")
        new_base_url = "http://minio:9000/test-bucket/new_prefix/"

        with mock.patch("ami.tasks.update_public_urls.delay") as mocked_task:
            self.source.public_base_url = new_base_url
            self.source.save()

        mocked_task.assert_called_once_with(deployment.pk, new_base_url)

    def test_saving_other_fields_does_not_update_capture_urls(self):
        self._create_deployment("Station With Captures")

        with mock.patch("ami.tasks.update_public_urls.delay") as mocked_task:
            self.source.name = "Renamed Source"
            self.source.save()

        mocked_task.assert_not_called()

    def test_creating_a_source_does_not_update_capture_urls(self):
        with mock.patch("ami.tasks.update_public_urls.delay") as mocked_task:
            S3StorageSource.objects.create(
                name="Brand New Source",
                project=self.project,
                bucket="test-bucket",
                public_base_url="http://minio:9000/test-bucket/",
            )

        mocked_task.assert_not_called()

    def test_update_public_urls_task_rewrites_every_capture(self):
        deployment = self._create_deployment("Station For Task")
        create_captures(deployment=deployment, num_nights=1, images_per_night=3)
        new_base_url = "http://minio:9000/test-bucket/new_prefix/"

        ami.tasks.update_public_urls(deployment.pk, new_base_url)

        base_urls = set(deployment.captures.values_list("public_base_url", flat=True))
        self.assertEqual(deployment.captures.count(), 3)
        self.assertEqual(base_urls, {new_base_url})
