import io
import logging

from django.conf import settings

from ami.main.models import Project, S3StorageSource
from ami.tests.fixtures.images import GeneratedTestFrame, generate_moth_series
from ami.utils import s3

logger = logging.getLogger(__name__)


S3_TEST_CONFIG = s3.S3Config(
    endpoint_url=settings.S3_TEST_ENDPOINT,
    access_key_id=settings.S3_TEST_KEY,
    secret_access_key=settings.S3_TEST_SECRET,
    bucket_name=settings.S3_TEST_BUCKET,
    region=settings.S3_TEST_REGION,
    prefix="test_prefix",
    public_base_url=f"http://minio:9000/{settings.S3_TEST_BUCKET}/test_prefix",
    # public_base_url="http://minio:9001",
)


def create_storage_source(project: Project, name: str, prefix: str = S3_TEST_CONFIG.prefix) -> S3StorageSource:
    s3.create_bucket(config=S3_TEST_CONFIG, bucket_name=S3_TEST_CONFIG.bucket_name)
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
            region=S3_TEST_CONFIG.region,
        ),
    )
    return data_source


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
            logging.info(f"Uploading {key} to {config.bucket_name}")
            s3.write_file(config, key, img_byte_arr)
            frame.object_store_key = key

            created.append(frame)

    return created
