import io
import logging

from django.conf import settings

from ami.main.models import Project, S3StorageSource
from ami.tests.fixtures.images import GeneratedTestFrame, generate_moth_series
from ami.utils import s3

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# CONFIG SELECTION
# - If AWS creds/bucket are present (EB/prod), use real AWS S3
# - Otherwise fall back to MinIO test config (original behavior)
# ---------------------------------------------------------------------

AWS_ACCESS_KEY = getattr(settings, "DJANGO_AWS_ACCESS_KEY_ID", None)
AWS_SECRET_KEY = getattr(settings, "DJANGO_AWS_SECRET_ACCESS_KEY", None)
AWS_BUCKET = getattr(settings, "DJANGO_AWS_STORAGE_BUCKET_NAME", None)

USE_AWS = all([AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_BUCKET])

if USE_AWS:
    # REAL AWS S3 CONFIG (for Elastic Beanstalk / production)
    S3_TEST_CONFIG = s3.S3Config(
        endpoint_url=None,  # boto3 will use AWS S3 automatically
        access_key_id=AWS_ACCESS_KEY,
        secret_access_key=AWS_SECRET_KEY,
        bucket_name=AWS_BUCKET,
        prefix="demo-data",
        public_base_url=f"https://{AWS_BUCKET}.s3.amazonaws.com/demo-data",
    )
    logger.info("[storage.py] Using AWS S3 config (DJANGO_AWS_* settings detected).")
else:
    # ORIGINAL MINIO TEST CONFIG (for local/test)
    S3_TEST_CONFIG = s3.S3Config(
        endpoint_url=getattr(settings, "S3_TEST_ENDPOINT", "http://minio:9000"),
        access_key_id=getattr(settings, "S3_TEST_KEY", "minioadmin"),
        secret_access_key=getattr(settings, "S3_TEST_SECRET", "minioadmin"),
        bucket_name=getattr(settings, "S3_TEST_BUCKET", "ami-test"),
        prefix="test_prefix",
        public_base_url=f"http://minio:9000/{getattr(settings, 'S3_TEST_BUCKET', 'ami-test')}/test_prefix",
    )
    logger.warning("[storage.py] Using MinIO test config (AWS settings not found).")


# ---------------------------------------------------------------------
# CREATE STORAGE SOURCE
# ---------------------------------------------------------------------
def create_storage_source(project: Project, name: str, prefix: str = S3_TEST_CONFIG.prefix) -> S3StorageSource:
    """
    Creates a S3StorageSource for tests/fixtures.

    - In MinIO mode: ensures the bucket exists (creates if missing).
    - In AWS mode: assumes bucket already exists (do not attempt create_bucket by default).
      (Creating real AWS buckets in test fixtures is usually not desired.)
    """
    if not USE_AWS:
        # Original behavior: ensure MinIO bucket exists
        s3.create_bucket(config=S3_TEST_CONFIG, bucket_name=S3_TEST_CONFIG.bucket_name)
    else:
        # Optional: lightweight prefix check (non-fatal)
        placeholder_key = f"{prefix}/.placeholder"
        try:
            s3.write_file(S3_TEST_CONFIG, placeholder_key, b"")
            logger.info(f"[S3] Verified prefix exists (AWS): {placeholder_key}")
        except Exception as e:
            logger.warning(f"[S3] Could not verify AWS prefix '{prefix}': {e}")

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
    # Images need to be named with iso timestamps to be sorted correctly
    # They should be in folders by day
    # the timestamps should range from 10pm to 4am over a few days
    created = []

    # Check if the subdir exists and already has images
    if skip_existing:
        keys = s3.list_files(config=config, subdir=subdir, limit=10)
        existing_keys = [key.key for key, i in keys if key]
        if existing_keys:
            logger.info(f"Skipping existing images in {subdir}: {existing_keys}")
            return []

    logger.info(f"Generating a total of {num_nights * images_per_day} images over {num_nights} nights")
    for _ in range(num_nights):
        for frame in generate_moth_series(
            num_frames=images_per_day,
            minutes_interval=minutes_interval,
            minutes_interval_variation=minutes_interval_variation,
            save_images=False,
        ):
            # Convert the image to bytes
            img_byte_arr = io.BytesIO()
            frame.image.save(img_byte_arr, format="JPEG")
            img_byte_arr = img_byte_arr.getvalue()

            # Create the S3 key for the image
            key = f"{subdir}/{frame.filename}"

            # Upload the image to S3
            logger.info(f"Uploading {key} to {config.bucket_name}")
            s3.write_file(config, key, img_byte_arr)
            frame.object_store_key = key

            created.append(frame)

    return created
