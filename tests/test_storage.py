import random

import botocore.exceptions
from django.conf import settings
from django.test import TestCase

from ami.utils import s3


class TestS3(TestCase):
    def setUp(self):
        self.config = s3.S3Config(
            endpoint_url=settings.S3_TEST_ENDPOINT,
            access_key_id=settings.S3_TEST_KEY,
            secret_access_key=settings.S3_TEST_SECRET,
            bucket_name=settings.S3_TEST_BUCKET,
            prefix="test_files",
        )
        client = s3.get_client(self.config)
        try:
            # Create bucket if it doesn't exist
            client.create_bucket(Bucket=self.config.bucket_name)
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
                raise

    def test_write_and_count(self):
        count = s3.count_files(self.config)
        test_key = f"test_{random.randint(0, 9999999)}"
        test_val = random.randbytes(5)
        s3.write_file(self.config, test_key, test_val)
        self.assertEqual(s3.count_files(self.config), count + 1)
        out_val = s3.read_file(self.config, test_key)
        self.assertEqual(test_val, out_val)
