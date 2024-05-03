import random
import string
from urllib.parse import parse_qs, urlparse

import botocore.exceptions
import requests
from django.conf import settings
from django.test import TestCase

from ami.utils import s3


def write_random_file(config: s3.S3Config) -> tuple[str, bytes]:
    test_key = f"test_{random.randint(0, 99999)}.txt"
    test_val = "".join(random.choice(string.ascii_letters) for _ in range(10)).encode("utf-8")
    s3.write_file(config, key=test_key, body=test_val)
    return test_key, test_val


class TestS3(TestCase):
    def setUp(self):
        self.config = s3.S3Config(
            endpoint_url=settings.S3_TEST_ENDPOINT,
            access_key_id=settings.S3_TEST_KEY,
            secret_access_key=settings.S3_TEST_SECRET,
            bucket_name=settings.S3_TEST_BUCKET,
            prefix="test_files",
            # public_base_url="http://minio:9001",
        )
        client = s3.get_client(self.config)
        try:
            # Create bucket if it doesn't exist
            client.create_bucket(Bucket=self.config.bucket_name)
        except botocore.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") != "BucketAlreadyOwnedByYou":
                raise

    def tearDown(self) -> None:
        client = s3.get_client(self.config)
        for f in s3.list_files(self.config):
            f.delete()
        client.delete_bucket(Bucket=self.config.bucket_name)

    def test_write_and_count(self):
        count = s3.count_files(self.config)
        test_key, test_val = write_random_file(self.config)
        self.assertEqual(s3.count_files(self.config), count + 1)
        out_val = s3.read_file(self.config, test_key)
        self.assertEqual(test_val, out_val)

    def test_presigned_url(self):
        test_key, test_val = write_random_file(self.config)
        url = s3.get_presigned_url(self.config, test_key)
        url_parts = urlparse(url)
        params = parse_qs(url_parts.query)

        # Test path is correct
        self.assertEqual(url_parts.path, f"/{self.config.bucket_name}/{self.config.prefix}/{test_key}")
        self.assertIn("X-Amz-Credential", params)

        # Test that the URL is accessible (minio is a dependency of the app container and should be running)
        resp = requests.get(url)
        resp.raise_for_status()

        # Test that the content is correct
        out_val = resp.content
        self.assertEqual(test_val, out_val)
