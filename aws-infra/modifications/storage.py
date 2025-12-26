"""

This module provides helper functions for setting up and working with
S3-based storage used by Antenna projects. 

## Function Overview
- create_storage_source(...)
  Called during project setup to ensure an S3 storage source exists
  and is accessible for a given Project.

- populate_bucket(...)
  Called only for demo or test setup to upload generated image data
  into S3/MinIO for pipeline validation.
  

## What Was Modified and Why
Previously, this module assumed a test-only MinIO setup and always tried
to create the S3 bucket at runtime.

This works locally, but causes issues in AWS because:
- S3 buckets already exist and are managed outside the application
- Attempting to create them again can fail or behave incorrectly

The logic was updated to:
- Automatically select AWS S3 in production and MinIO locally
- Assume the bucket already exists in AWS
- Verify access by writing a small placeholder file instead of creating
  the bucket

This allows the same code to run safely in both local and AWS
environments without duplication.

"""



import io
import logging

from django.conf import settings

from ami.main.models import Project, S3StorageSource
from ami.tests.fixtures.images import GeneratedTestFrame, generate_moth_series
from ami.utils import s3

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# SAFE CONFIG LOGIC
# Uses REAL AWS S3 in production (EB)
# Uses FALLBACK MINIO fake config during Docker build / test mode
# ---------------------------------------------------------------------

USE_AWS = all([
    hasattr(settings, "DJANGO_AWS_ACCESS_KEY_ID"),
    hasattr(settings, "DJANGO_AWS_SECRET_ACCESS_KEY"),
    hasattr(settings, "DJANGO_AWS_STORAGE_BUCKET_NAME"),
])

if USE_AWS:
    # REAL AWS CONFIG  (for Elastic Beanstalk)
    S3_TEST_CONFIG = s3.S3Config(
        endpoint_url=None,  # boto3 auto-selects correct S3 endpoint
        access_key_id=settings.DJANGO_AWS_ACCESS_KEY_ID,
        secret_access_key=settings.DJANGO_AWS_SECRET_ACCESS_KEY,
        bucket_name=settings.DJANGO_AWS_STORAGE_BUCKET_NAME,
        prefix="demo-data",
        public_base_url=f"https://{settings.DJANGO_AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/demo-data",
    )
else:
    # FALLBACK CONFIG (for Docker build/test)
    S3_TEST_CONFIG = s3.S3Config(
        endpoint_url="http://minio:9000",
        access_key_id="minioadmin",
        secret_access_key="minioadmin",
        bucket_name="ami-test",
        prefix="test_prefix",
        public_base_url="http://minio:9000/ami-test/test_prefix",
    )
    logger.warning("Using fallback MinIO test config (AWS settings not found).")


# ---------------------------------------------------------------------
# CREATE STORAGE SOURCE
# ---------------------------------------------------------------------
def create_storage_source(project: Project, name: str, prefix: str = S3_TEST_CONFIG.prefix) -> S3StorageSource:

    # Try creating tiny placeholder to verify prefix
    placeholder_key = f"{prefix}/.placeholder"

    try:
        s3.write_file(S3_TEST_CONFIG, placeholder_key, b"")
        logger.info(f"[S3] Verified prefix exists: {placeholder_key}")
    except Exception as e:
        logger.error(f"[S3] Could not verify prefix '{prefix}': {e}")

    data_source, _created = S3StorageSource.objects.get_or_create(
        project=project,
        name=name,
        defaults=dict(
            bucket=S3_TEST_CONFIG.bucket_name,
            prefix=prefix,
            endpoint_url=S3_TEST_CONFIG.endpoint_url,
            access_key=S3_TEST_CONFIG.access_key_id,
            secret_key=S3_TEST_CONFIG.secret_access_key,
            public_base_url=S3_TEST_CONFIG.public_base_url,
        ),
    )

    return data_source


# ---------------------------------------------------------------------
# POPULATE BUCKET WITH DEMO IMAGES
# ---------------------------------------------------------------------
def populate_bucket(
    config: s3.S3Config,
    subdir: str = "deployment_1",
    num_nights: int = 2,
    images_per_day: int = 3,
    minutes_interval: int = 45,
    minutes_interval_variation: int = 10,
    skip_existing: bool = True,
) -> list[GeneratedTestFrame]:

    created = []

    # Skip if images already exist
    if skip_existing:
        keys = s3.list_files(config=config, subdir=subdir, limit=10)
        existing_keys = [key.key for key, i in keys if key]

        if existing_keys:
            logger.info(f"[S3] Skipping: Found existing images in {subdir}: {existing_keys}")
            return []

    logger.info(f"[S3] Generating {num_nights * images_per_day} demo frames…")

    for _ in range(num_nights):
        for frame in generate_moth_series(
            num_frames=images_per_day,
            minutes_interval=minutes_interval,
            minutes_interval_variation=minutes_interval_variation,
            save_images=False,
        ):

            # Convert image to bytes
            img_bytes = io.BytesIO()
            frame.image.save(img_bytes, format="JPEG")
            img_bytes = img_bytes.getvalue()

            # S3 key
            key = f"{subdir}/{frame.filename}"

            logger.info(f"[S3] Uploading: {key} → {config.bucket_name}")
            s3.write_file(config, key, img_bytes)

            frame.object_store_key = key
            created.append(frame)

    return created
