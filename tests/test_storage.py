import logging
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from django.test import TestCase

from ami.main.models import S3StorageSource
from ami.utils import s3
from tests.fixtures.main import create_captures, setup_test_project
from tests.fixtures.storage import S3_TEST_CONFIG

logger = logging.getLogger(__name__)


class TestS3(TestCase):
    def setUp(self):
        self.config = S3_TEST_CONFIG
        s3.create_bucket(self.config, self.config.bucket_name)

    def tearDown(self) -> None:
        bucket = s3.get_bucket(self.config)
        bucket.objects.all().delete()
        bucket.object_versions.delete()
        bucket.delete()

    def test_connection_no_files(self):
        result = s3.test_connection(self.config)
        self.assertTrue(result.connection_successful)
        self.assertIsNone(result.first_file_found)
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
            endpoint_url="http://localhost:9000",
            access_key_id="minioadmin",
            secret_access_key="minioadmin",
            bucket_name="test_bucket",
            prefix="test_prefix",
            public_base_url="http://localhost:9000/test",
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
        self.captures = create_captures(self.deployment)
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

    def test_public_url(self):
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
