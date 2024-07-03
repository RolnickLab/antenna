import io
import logging
import pathlib
import re
import time
import typing
import urllib.parse
from dataclasses import dataclass

import boto3
import boto3.resources.base
import botocore
import botocore.config
import botocore.exceptions
import PIL
import PIL.Image

# @TODO don't use Django cache in utils if possible
from django.core.cache import cache
from mypy_boto3_s3.client import S3Client
from mypy_boto3_s3.paginator import ListObjectsV2Paginator
from mypy_boto3_s3.service_resource import Bucket, ObjectSummary, S3ServiceResource
from mypy_boto3_s3.type_defs import BucketTypeDef, ObjectTypeDef, PaginatorConfigTypeDef
from rich import print

from .storages import ConnectionTestResult

logger = logging.getLogger(__name__)


@dataclass
class S3Config:
    endpoint_url: str | None
    access_key_id: str
    secret_access_key: str
    bucket_name: str
    prefix: str
    public_base_url: str | None = None

    sensitive_fields = ["access_key_id", "secret_access_key"]

    def safe_dict(self):
        return {k: v for k, v in self.__dict__.items() if k not in self.sensitive_fields}

    def safe_hash(self):
        return "-".join(map(str, self.safe_dict().values()))


def with_trailing_slash(s: str):
    return s if s.endswith("/") else f"{s}/"


def without_trailing_slash(s: str):
    return s.rstrip("/")


def with_leading_slash(s: str):
    return s if s.startswith("/") else f"/{s}"


def without_leading_slash(s: str):
    return s.lstrip("/")


def split_uri(s3_uri: str):
    """
    Split S3 URI into bucket and prefix
    # s3://<BUCKET>/<PREFIX>/<SUBPREFIX>
    """

    # If filename in path, remove it
    if "." in s3_uri.split("/")[-1]:
        s3_uri = "/".join(s3_uri.split("/")[:-1])

    path = s3_uri.replace("s3://", "")
    bucket, *prefix = path.split("/")
    prefix = "/".join(prefix)
    return bucket, prefix


def join_path(*parts: str) -> str:
    """
    Join a list of strings so that there is a single slash between each part,
    a trailing slash at the end, and a leading slash at the beginning.
    """
    parts = tuple(str(p).strip("/") for p in parts)
    path = "/".join(parts)
    return f"/{path}/"


def get_session(config: S3Config) -> boto3.session.Session:
    session = boto3.Session(
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
    )
    return session


def get_client(config: S3Config) -> S3Client:
    session = get_session(config)
    if config.endpoint_url:
        client: S3Client = session.client(
            service_name="s3",
            endpoint_url=config.endpoint_url,
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            config=botocore.config.Config(signature_version="s3v4"),
        )
    else:
        client: S3Client = session.client(
            service_name="s3",
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
        )

    return client


def get_resource(config: S3Config) -> S3ServiceResource:
    session = get_session(config)
    s3 = session.resource(
        "s3",
        endpoint_url=config.endpoint_url,
        # api_version="s3v4",
    )
    return s3


def list_buckets(config: S3Config) -> list[BucketTypeDef]:
    s3 = get_client(config)
    return s3.list_buckets().get("Buckets", [])


def get_bucket(config: S3Config) -> Bucket:
    s3 = get_resource(config)
    bucket = s3.Bucket(config.bucket_name)
    return bucket


def list_projects(config: S3Config):
    client = get_client(config)
    resp = client.list_objects_v2(Bucket=config.bucket_name, Prefix="", Delimiter="/")
    prefixes = [without_trailing_slash(item["Prefix"]) for item in resp["CommonPrefixes"]]  # type: ignore
    return prefixes


def list_deployments(config: S3Config, project: str):
    client = get_client(config)
    resp = client.list_objects_v2(Bucket=config.bucket_name, Prefix=with_trailing_slash(project), Delimiter="/")
    if len(resp) and "CommonPrefixes" in resp.keys():
        prefixes = [without_trailing_slash(item["Prefix"]) for item in resp["CommonPrefixes"]]  # type: ignore
    else:
        prefixes = []
    return prefixes


def count_files(config: S3Config):
    bucket = get_bucket(config)
    count = sum(1 for _ in bucket.objects.filter(Prefix=config.prefix).all())
    return count


def count_files_paginated(config: S3Config) -> int:
    client = get_client(config)
    paginator: ListObjectsV2Paginator = client.get_paginator("list_objects_v2")
    page_iterator = paginator.paginate(
        Bucket=config.bucket_name,
        Prefix=config.prefix,
        PaginationConfig={
            "PageSize": 10000,
        },  # "MaxItems": 1000000}
    )
    count = 0
    for page in page_iterator:
        count += page["KeyCount"]
    return count


def list_files(
    config: S3Config,
    limit: int | None = 100000,
    subdir: str | None = None,
    regex_filter: str | None = None,
) -> typing.Generator[ObjectSummary, typing.Any, None]:
    # @TODO raise a warning about potential cost for large buckets
    bucket = get_bucket(config)
    full_prefix = make_full_prefix(config, subdir)
    logger.debug(f"Scanning {make_full_prefix_uri(config, subdir, regex_filter)}")
    q = bucket.objects.filter(Prefix=full_prefix)
    if limit:
        objects = q.limit(limit).all()
    else:
        objects = q.all()
    bucket_iter = objects
    regex = re.compile(str(regex_filter)) if regex_filter else None
    for obj in bucket_iter:
        if obj.key.endswith("/"):
            logger.debug(obj.key + " is skipped because it is a folder")
            continue
        if regex and not regex.match(obj.key):
            logger.debug(obj.key + " is skipped by regex filter")
            continue
        logger.debug(f"Yielding {obj.key}")
        yield obj


def make_full_prefix(
    config: S3Config, subdir: str | None = None, with_bucket: bool = False, leading_slash: bool = False
) -> str:
    full_prefix = pathlib.Path(config.prefix, subdir or "").as_posix()
    if with_bucket:
        full_prefix = pathlib.Path(config.bucket_name, full_prefix).as_posix()
    if leading_slash:
        full_prefix = with_leading_slash(full_prefix)
    full_prefix = with_trailing_slash(full_prefix)
    return full_prefix


def key_with_prefix(config: S3Config, key: str, subdir: str | None = None, leading_slash: bool = False) -> str:
    """
    Constructs the full key with prefix and subdir for an S3 object.
    Supports checking if the prefix and subdir are already included in the key.

    Args:
        config (S3Config): The S3 configuration object.
        key (str): The key of the S3 object.
        subdir (str | None, optional): The subdirectory within the S3 bucket. Defaults to None.
        leading_slash (bool, optional): Whether to include a leading slash in the prefix. Defaults to False.

    Returns:
        str: The full key with prefix for the S3 object.
    """
    full_prefix = make_full_prefix(config, subdir, leading_slash=leading_slash)

    key = key.lstrip("/")

    # Ensure the key starts with the full prefix and does not duplicate the prefix or subdir
    if key.startswith(full_prefix.lstrip("/")):
        return key
    elif subdir:
        subdir = subdir.strip("/")
        key = key.split(subdir, 1)[-1]

    full_key = pathlib.Path(full_prefix, key.lstrip("/")).as_posix()

    return full_key


def make_full_prefix_uri(config: S3Config, subdir: str | None = None, regex_filter: str | None = None) -> str:
    full_prefix = make_full_prefix(config, subdir, with_bucket=True, leading_slash=False)
    uri = f"s3://{full_prefix}"
    if regex_filter:
        uri = f"{uri}?regex={urllib.parse.quote_plus(regex_filter)}"
    return uri


def make_full_key_uri(config: S3Config, key: str, subdir: str | None = None, with_protocol: bool = True) -> str:
    """
    Useful when you need the full S3 URI for a key or the full path to a key that includes the bucket name.
    """
    key = key_with_prefix(config, key, subdir)
    if with_protocol:
        full_key_uri = f"s3://{pathlib.Path(config.bucket_name, key).as_posix()}"
    else:
        full_key_uri = f"/{pathlib.Path(config.bucket_name, key).as_posix()}"

    return full_key_uri


def filter_objects(
    page_iterator, regex_filter: str | None = None
) -> typing.Generator[ObjectTypeDef, typing.Any, None]:
    """
    Filter objects based on regex pattern and yield matching objects.
    """
    regex = re.compile(str(regex_filter)) if regex_filter else None
    logger.debug(f"Filtering objects with regex: {regex}")

    for page in page_iterator:
        if "Contents" in page:
            for obj in page["Contents"]:
                assert "Key" in obj, f"Key is missing from object: {obj}"
                logger.debug(f"Found {obj['Key']}")
                if obj["Key"].endswith("/"):
                    logger.debug(obj["Key"] + " is skipped because it is a folder")
                    continue
                if regex and not regex.search(str(obj["Key"])):
                    logger.debug(f'{obj["Key"]} is skipped by regex filter: "{regex.pattern}"')
                    continue
                logger.debug(f"Yielding {obj['Key']}")
                yield obj
        else:
            logger.debug("No Contents in page")


def list_files_paginated(
    config: S3Config,
    subdir: str | None = None,
    regex_filter: str | None = None,
    max_keys: int | None = None,
    **paginator_params: typing.Any,
) -> typing.Generator[ObjectTypeDef, None, None]:
    """
    List files in a bucket, with pagination to increase performance.
    """
    client = get_client(config)
    full_prefix = make_full_prefix(config, subdir)
    full_uri = make_full_prefix_uri(config, subdir, regex_filter)
    logger.info(f"Scanning {full_uri}")
    paginator: ListObjectsV2Paginator = client.get_paginator("list_objects_v2")

    # Prepare paginator parameters
    paginate_params: dict[str, typing.Any] = {
        "Bucket": config.bucket_name,
        "Prefix": full_prefix,
    }

    # Prepare pagination configuration
    pagination_config: PaginatorConfigTypeDef = {}
    if max_keys is not None:
        pagination_config["MaxItems"] = max_keys

    # Update with any additional paginator parameters
    paginate_params.update(paginator_params)

    # Use the Prefix parameter to filter results server-side
    page_iterator = paginator.paginate(PaginationConfig=pagination_config, **paginate_params)

    # Use a separate generator for regex filtering
    return filter_objects(page_iterator, regex_filter)


def _handle_boto_error(e: Exception) -> tuple[str, str]:
    """Handle different types of boto errors and return appropriate error code and message."""
    if isinstance(e, botocore.exceptions.ClientError):
        error_code = e.response.get("Error", {}).get("Code", "UnknownBotoError")
        error_message = e.response.get("Error", {}).get("Message", str(e))
    elif isinstance(e, botocore.exceptions.EndpointConnectionError):
        error_code = "EndpointConnectionError"
        error_message = str(e)
    elif isinstance(e, botocore.exceptions.BotoCoreError):
        error_code = e.__class__.__name__
        error_message = str(e)
    else:
        error_code = "UnknownBotoError"
        error_message = str(e)

    logger.error(f"{error_code}: {error_message}")
    return error_code, error_message


def test_connection(
    config: S3Config, subdir: str | None = None, regex_filter: str | None = None
) -> ConnectionTestResult:
    """
    Test the connection and return detailed statistics about the operation.
    """
    connection_successful = False
    start_time = time.time()
    latency = None
    prefix_exists = False
    files_checked = 0
    first_file_found = None
    error_code = None
    error_message = None

    full_uri = make_full_prefix_uri(config, subdir, regex_filter)

    try:
        # Determine max_keys based on whether a regex_filter is provided
        max_keys = 1 if not regex_filter else 10000
        files_checked = max_keys

        # Use list_files_paginated with appropriate max_keys
        file_generator = list_files_paginated(config, subdir, regex_filter, max_keys=max_keys)

        # Measure latency to first response
        first_response_time = time.time()
        latency = first_response_time - start_time

        first_file_found = next(file_generator, None)

        connection_successful = True
        prefix_exists = first_file_found is not None  # In S3, a prefix only exists if there is at least one object

    except (
        botocore.exceptions.ClientError,
        botocore.exceptions.EndpointConnectionError,
        botocore.exceptions.BotoCoreError,
    ) as e:
        error_code, error_message = _handle_boto_error(e)
    except Exception as e:
        error_code = "UnknownError"
        error_message = str(e)
        logger.error(f"Unknown error: {error_message}")
        raise  # Re-raise the exception for unexpected errors

    total_time = time.time() - start_time

    first_file_key = first_file_found.get("Key") if first_file_found else None
    if first_file_key:
        first_file_url = public_url(config, first_file_key)
    else:
        first_file_url = None

    result = ConnectionTestResult(
        connection_successful=connection_successful,
        prefix_exists=prefix_exists,
        latency=latency if latency is not None else total_time,
        total_time=total_time,
        error_message=error_message,
        error_code=error_code,
        files_checked=files_checked,
        first_file_found=first_file_url,
        full_uri=full_uri,
    )
    return result


def read_file(config: S3Config, key: str) -> bytes:
    bucket = get_bucket(config)
    key = key_with_prefix(config, key)
    obj = bucket.Object(key)
    logger.debug(f"Reading file from {make_full_key_uri(config, obj.key)}")
    return obj.get()["Body"].read()


def write_file(config: S3Config, key: str, body: bytes):
    bucket = get_bucket(config)
    key = key_with_prefix(config, key)
    obj = bucket.Object(key)
    obj.put(Body=body)
    logger.debug(f"Uploaded file to {make_full_key_uri(config, obj.key)}")
    return obj


def file_exists(config: S3Config, key: str) -> bool:
    bucket = get_bucket(config)
    if config.prefix:
        # Use path join to ensure there are no extra or missing slashes
        key = pathlib.Path(config.prefix, key).as_posix()
    obj = bucket.Object(key)
    try:
        obj.load()
    except botocore.exceptions.ClientError as e:
        if e.response.get("Error", {}).get("Code") == "404":
            return False
        else:
            raise
    else:
        return True


def read_image(config: S3Config, key: str) -> PIL.Image.Image:
    """
    Download an image from S3 and return as a PIL Image.
    """
    bucket = get_bucket(config)
    obj = bucket.Object(key)
    logger.info(f"Fetching image {key} from S3")
    try:
        img = PIL.Image.open(obj.get()["Body"])
    except PIL.UnidentifiedImageError:
        logger.error(f"Could not read image {key}")
        raise
    return img


def public_url(config: S3Config, key: str):
    """
    Return public URL for a given key.

    @TODO Handle non-public buckets with signed URLs
    """
    if not config.public_base_url:
        return get_presigned_url(config, key)
    else:
        # return urllib.parse.urljoin(config.public_base_url, key.lstrip("/"))
        return urllib.parse.urljoin(config.public_base_url, make_full_key_uri(config, key, with_protocol=False))


def get_presigned_url(config: S3Config, key: str, expires_in: int = 60 * 60 * 24 * 7) -> str:
    """
    Generate a presigned URL for a given key.
    """
    cache_key = f"s3_presigned_url:{config.safe_hash()}:{key}"
    url = cache.get(cache_key, default=None)
    if not url:
        logger.debug(f"Fetching new presigned URL for: {cache_key}")
        client = get_client(config)
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": config.bucket_name, "Key": key},
            ExpiresIn=expires_in,
        )
        cache.set(cache_key, url, timeout=expires_in)
    else:
        logger.debug(f"Got cached presigned URL for: {cache_key}")
    return str(url)


# Methods to resize all images under a prefix
def resize_images(config: S3Config, prefix: str, width: int, height: int):
    bucket = get_bucket(config)
    objects = bucket.objects.filter(Prefix=with_trailing_slash(prefix)).all()
    for obj in objects:
        resize_image(config, obj.key, width, height)


def resized_key(config: S3Config, key: str, width: int, height: int):
    path = pathlib.Path(key)
    new_prefix = f"/resized/{without_trailing_slash(config.prefix)}/{path.parent.name}"
    new_key = f"{new_prefix}/{path.stem}_{width}x{height}.{path.suffix}"
    return new_key


def resize_image(config: S3Config, key: str, width: int, height: int) -> str:
    client = get_client(config)
    new_key = resized_key(config, key, width, height)
    client.put_object(
        Bucket=config.bucket_name,
        Key=new_key,
        Body=resize_image_body(client, config.bucket_name, key, width, height),
    )
    return new_key


def resize_image_body(client: S3Client, bucket: str, key: str, width: int, height: int) -> bytes:
    body = client.get_object(Bucket=bucket, Key=key)["Body"].read()
    image = PIL.Image.open(io.BytesIO(body))
    image.thumbnail((width, height))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def test():
    # boto3.set_stream_logger(name="botocore")

    config = S3Config(
        endpoint_url="http://localhost:9000",
        access_key_id="minioadmin",
        secret_access_key="minioadmin",
        bucket_name="test",
        prefix="",
        public_base_url="http://localhost:9000/test",
    )

    projects = list_projects(config)
    print("Projects:", projects)
    for project in projects:
        deployments = list_deployments(config, project)
        print("\tDeployments:", deployments)

        for deployment in deployments:
            # print("\t\tFile Count:", count_files(deployment))

            for file in list_files(config, limit=1):
                print(file)
                print("\t\t\tSample:", public_url(config, file.key))
