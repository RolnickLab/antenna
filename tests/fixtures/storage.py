from django.conf import settings

from ami.main.models import Project, S3StorageSource
from ami.utils import s3

S3_TEST_CONFIG = s3.S3Config(
    endpoint_url=settings.S3_TEST_ENDPOINT,
    access_key_id=settings.S3_TEST_KEY,
    secret_access_key=settings.S3_TEST_SECRET,
    bucket_name=settings.S3_TEST_BUCKET,
    prefix="test_prefix",
    # public_base_url="http://localhost:9000/test",
    # public_base_url="http://minio:9001",
)


def create_storage_source(project: Project, name: str) -> S3StorageSource:
    s3.create_bucket(config=S3_TEST_CONFIG, bucket_name=S3_TEST_CONFIG.bucket_name)
    data_source, _created = S3StorageSource.objects.get_or_create(
        project=project,
        name=name,
        defaults=dict(
            bucket=S3_TEST_CONFIG.bucket_name,
            prefix=S3_TEST_CONFIG.prefix,
            endpoint_url=S3_TEST_CONFIG.endpoint_url,
            access_key=S3_TEST_CONFIG.access_key_id,
            secret_key=S3_TEST_CONFIG.secret_access_key,
            public_base_url=S3_TEST_CONFIG.public_base_url,
        ),
    )
    return data_source
