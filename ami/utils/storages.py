import urllib.parse
from dataclasses import dataclass

from storages.backends.s3boto3 import S3Boto3Storage

IMAGE_FILE_EXTENSIONS = ["jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "ico", "tiff", "tif"]


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


# @TODO move to settings & make configurable
TEMPORARY_SOURCE_IMAGES_URL_BASE = "https://static.dev.insectai.org/ami-trapdata/vermont/snapshots/"
TEMPORARY_CROPS_URL_BASE = "https://static.dev.insectai.org/ami-trapdata/crops"


def get_temporary_media_url(path: str) -> str:
    """
    If path is a full URL, return it as-is.
    Otherwise, join it with the MEDIA_URL setting.
    """
    # @TODO use settings
    # urllib.parse.urljoin(settings.MEDIA_URL, self.path)
    if path.startswith("http"):
        url = path
    else:
        url = urllib.parse.urljoin(TEMPORARY_CROPS_URL_BASE, path.lstrip("/"))
    return url
