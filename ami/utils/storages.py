from dataclasses import dataclass

from storages.backends.s3boto3 import S3Boto3Storage


class StaticRootS3Boto3Storage(S3Boto3Storage):
    location = "static"
    default_acl = "public-read"


class MediaRootS3Boto3Storage(S3Boto3Storage):
    location = "media"
    file_overwrite = False


@dataclass
class ConnectionTestResult:
    connection_successful: bool
    prefix_exists: bool
    latency: float
    total_time: float
    error_code: str | None
    error_message: str | None
    files_checked: int
    first_file_found: str | None
    full_uri: str | None
