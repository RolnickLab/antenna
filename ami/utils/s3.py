import io
import logging
import pathlib
import random
import re
import string
import time
import typing
import urllib.parse
from dataclasses import dataclass

import boto3
import boto3.session
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
from mypy_boto3_s3.type_defs import BucketTypeDef, CreateBucketOutputTypeDef, ObjectTypeDef, PaginatorConfigTypeDef
from rich import print

from .storages import IMAGE_FILE_EXTENSIONS, ConnectionTestResult

logger = logging.getLogger(__name__)


@dataclass
class S3Config:
    endpoint_url: str | None
    access_key_id: str
    secret_access_key: str
    bucket_name: str
    prefix: str
    region: str | None = None
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
        region_name=config.region,
    )
    return session


def get_s3_client(config: S3Config) -> S3Client:
    session = get_session(config)

    # Always use signature version 4
    boto_config = botocore.config.Config(signature_version="s3v4")

    if config.endpoint_url:
        client = session.client(
            service_name="s3",
            endpoint_url=config.endpoint_url,
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            region_name=config.region,
            config=boto_config,
        )
    else:
        client = session.client(
            service_name="s3",
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            region_name=config.region,
            config=boto_config,
        )

    client = typing.cast(S3Client, client)
    return client


def get_resource(config: S3Config) -> S3ServiceResource:
    session = get_session(config)
    boto_config = botocore.config.Config(signature_version="s3v4")
    s3 = session.resource(
        "s3",
        endpoint_url=config.endpoint_url,
        region_name=config.region,
        config=boto_config,
    )
    s3 = typing.cast(S3ServiceResource, s3)
    return s3


def create_bucket(config: S3Config, bucket_name: str, exists_ok: bool = True) -> CreateBucketOutputTypeDef | None:
    """
    Create an S3 bucket.

    Note: This is primarily used for testing. In production, users are expected to
    create their own buckets and provide credentials to Antenna.

    Args:
        config: S3 configuration including region
        bucket_name: Name of the bucket to create
        exists_ok: If True, don't raise an error if bucket already exists

    Returns:
        CreateBucketOutputTypeDef or None if bucket already exists and exists_ok=True
    """
    client = get_s3_client(config)
    try:
        # AWS requires CreateBucketConfiguration for non-us-east-1 regions
        # See: https://docs.aws.amazon.com/AmazonS3/latest/API/API_CreateBucket.html
        if config.region and config.region != "us-east-1":
            return client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": config.region},
            )
        else:
            # us-east-1 or no region (Swift/MinIO) - don't specify CreateBucketConfiguration
            return client.create_bucket(Bucket=bucket_name)
    except botocore.exceptions.ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "UnknownBotoError")
        if error_code == "BucketAlreadyOwnedByYou" and exists_ok:
            pass
        else:
            raise


def list_buckets(config: S3Config) -> list[BucketTypeDef]:
    s3 = get_s3_client(config)
    return s3.list_buckets().get("Buckets", [])


def get_bucket(config: S3Config) -> Bucket:
    s3 = get_resource(config)
    bucket = s3.Bucket(config.bucket_name)
    return bucket


def list_projects(config: S3Config):
    client = get_s3_client(config)
    resp = client.list_objects_v2(Bucket=config.bucket_name, Prefix="", Delimiter="/")
    prefixes = [without_trailing_slash(item["Prefix"]) for item in resp["CommonPrefixes"]]  # type: ignore
    return prefixes


def list_deployments(config: S3Config, project: str):
    client = get_s3_client(config)
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
    client = get_s3_client(config)
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


def _compile_regex_filter(regex_filter: str | None) -> re.Pattern | None:
    regex = re.compile(str(regex_filter)) if regex_filter else None
    if regex:
        logger.debug(f"Interpreted regex_filter '{regex_filter}' as pattern '{regex.pattern}'")
    return regex


def _filter_single_key(
    key: str,
    obj_size: int,
    regex: re.Pattern | None = None,
    file_extensions: list[str] = IMAGE_FILE_EXTENSIONS,
) -> bool:
    """
    Determine if a single filepath should be filtered based on a regex pattern.
    """
    logger.debug(f"Checking key: {key}")
    if key == "":
        logger.debug("Empty key is skipped")
        return False
    if not any(key.lower().endswith(ext) for ext in file_extensions):
        logger.debug(f"{key} is skipped because it does not have a valid file extension: {file_extensions}")
        return False
    if key.endswith("/"):
        logger.debug(key + " is skipped because it is a folder")
        return False
    if regex and not regex.search(key):
        logger.debug(f'{key} is skipped by regex filter: "{regex.pattern}"')
        return False
    if obj_size == 0:
        logger.debug(f"{key} is skipped because it is an empty object")
        return False
    return True


def list_files(
    config: S3Config,
    limit: int | None = 100000,
    subdir: str | None = None,
    regex_filter: str | None = None,
    file_extensions: list[str] = IMAGE_FILE_EXTENSIONS,
) -> typing.Generator[tuple[ObjectSummary | None, int], typing.Any, None]:
    """
    "Recursively" list files in a bucket, with optional limit and regex filter.

    Returns an ObjectSummary object.

    @TODO Consider returning just the key instead of the full object so we
    can make list_files_paginated more consistent with list_files.
    """
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
    regex = _compile_regex_filter(regex_filter)
    num_files_checked = 0
    for num_files_checked, obj in enumerate(bucket_iter):
        num_files_checked += 1
        if _filter_single_key(obj.key, obj_size=obj.size, regex=regex, file_extensions=file_extensions):
            logger.debug(f"Yielding {obj.key}")
            yield obj, num_files_checked
    yield None, num_files_checked


def list_files_paginated(
    config: S3Config,
    limit: int | None = None,
    subdir: str | None = None,
    regex_filter: str | None = None,
    file_extensions: list[str] = IMAGE_FILE_EXTENSIONS,
    **paginator_params: typing.Any,
) -> typing.Generator[tuple[ObjectTypeDef | None, int], typing.Any, None]:
    """
    List files in a bucket, with pagination to increase performance.

    Returns an ObjectTypeDef dict instead of an ObjectSummary object.

    @TODO Consider returning just the key instead of the full object so we
    can make list_files_paginated more consistent with list_files.
    """
    client = get_s3_client(config)
    full_prefix = make_full_prefix(config, subdir)
    full_uri = make_full_prefix_uri(config, subdir, regex_filter)
    logger.info(f"Scanning {full_uri}")
    paginator: ListObjectsV2Paginator = client.get_paginator("list_objects_v2")

    # Prepare paginator parameters
    paginate_params: dict[str, typing.Any] = {
        "Bucket": config.bucket_name,
    }
    if full_prefix:
        paginate_params["Prefix"] = full_prefix

    # Prepare pagination configuration
    pagination_config: PaginatorConfigTypeDef = {}
    if limit is not None:
        pagination_config["MaxItems"] = limit

    # Use the Prefix parameter to filter results server-side
    page_iterator = paginator.paginate(PaginationConfig=pagination_config, **paginate_params)

    regex = _compile_regex_filter(regex_filter)

    num_files_checked = 0
    for i, page in enumerate(page_iterator):
        if "Contents" in page:
            for obj in page["Contents"]:
                num_files_checked += 1
                assert "Key" in obj and "Size" in obj, f"Key or Size is missing from object: {obj}"
                logger.debug(f"Found {obj['Key']}")
                if _filter_single_key(obj["Key"], obj_size=obj["Size"], regex=regex, file_extensions=file_extensions):
                    logger.debug(f"Yielding {obj['Key']}")
                    yield obj, num_files_checked
        else:
            logger.debug("No Contents in page")

    yield None, num_files_checked


def make_full_prefix(
    config: S3Config, subdir: str | None = None, with_bucket: bool = False, leading_slash: bool = False
) -> str:
    full_prefix = pathlib.Path(without_leading_slash(config.prefix), without_leading_slash(subdir) if subdir else "")
    if with_bucket:
        full_prefix = pathlib.Path(config.bucket_name, full_prefix)

    full_prefix = full_prefix.as_posix()
    if leading_slash:
        full_prefix = with_leading_slash(full_prefix)
    full_prefix = with_trailing_slash(full_prefix)

    # Fix for empty prefix that pathlib resolves to "./" which breaks in MinIO
    if pathlib.Path(full_prefix) == pathlib.Path():
        full_prefix = ""

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
        full_key_uri = f"s3://{pathlib.Path(config.bucket_name, without_leading_slash(key)).as_posix()}"
    else:
        full_key_uri = f"/{pathlib.Path(config.bucket_name, without_leading_slash(key)).as_posix()}"

    return full_key_uri


def _handle_boto_error(e: Exception, operation_name: str = "unknown_operation", raise_error=False) -> tuple[str, str]:
    """Handle different types of boto errors and return more specific exceptions."""

    known_errors = {
        "NoSuchKey": ("InvalidCredentials", "Invalid access key"),
        "AccessDenied": ("InvalidCredentials", "Invalid secret key or insufficient permissions"),
        "NoSuchBucket": ("NoSuchBucket", "Bucket does not exist"),
    }

    if isinstance(e, botocore.exceptions.ClientError):
        error_code = e.response.get("Error", {}).get("Code", "UnknownBotoError")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        if error_code in known_errors:
            error_code, error_message = known_errors[error_code]

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
    if raise_error:
        raise botocore.exceptions.ClientError(
            {"Error": {"Code": error_code, "Message": error_message}},
            operation_name=operation_name,
        )
    else:
        return error_code, error_message


def test_credentials(config: S3Config) -> bool:
    client = get_s3_client(config)
    try:
        client.get_bucket_location(Bucket=config.bucket_name)
    except botocore.exceptions.ClientError as e:
        _handle_boto_error(e, operation_name="get_bucket_location", raise_error=True)
    return True


def delete_blank_and_empty_key(config: S3Config, subdir: str | None = None):
    """
    Apparently MinIO and Swift object store allows you to create objects with no name,
    which breaks the list_files function.

    Here we will delete any objects with no name if their content length is 0.
    """
    key = key_with_prefix(config, "", subdir)
    if file_exists(config, key):
        key = get_bucket(config).Object(key)
        # Check if the object content length is 0
        if key.get()["ContentLength"] == 0:
            logger.warn(f"Found object with no name, deleting empty object at: {key}")
            key.delete()
        else:
            logger.error(
                f"Object with no name has content, skipping deletion of: {key}, but list_files function may break"
            )


def test_connection(
    config: S3Config,
    subdir: str | None = None,
    regex_filter: str | None = None,
    file_extensions: list[str] = IMAGE_FILE_EXTENSIONS,
) -> ConnectionTestResult:
    """
    Test the connection and return detailed statistics about the operation.
    """
    connection_successful = False
    start_time = time.time()
    latency = None
    prefix_exists = False
    num_files_checked = 0
    first_file_found = None
    error_code = None
    error_message = None

    full_uri = make_full_prefix_uri(config, subdir, regex_filter)

    try:
        # Test the access key & secret credentials by calling STS
        test_credentials(config)

        # Limit the number of files to check
        limit = 10000

        # Delete blank keys at this subdirectory level
        # @TODO Needs further testing. This fixed the issue, but also increasing the limit fixed the issue.
        # delete_blank_and_empty_key(config, subdir)

        # Use list_files_paginated with appropriate max_keys
        file_generator = list_files_paginated(
            config,
            limit=limit,
            subdir=subdir,
            regex_filter=regex_filter,
            file_extensions=file_extensions,
        )

        # Measure latency to first response
        first_response_time = time.time()
        latency = first_response_time - start_time

        first_file_found, num_files_checked = next(file_generator, (None, 0))

        connection_successful = True
        prefix_exists = first_file_found is not None  # In S3, a prefix only exists if there is at least one object

        if num_files_checked == 0:
            error_code = "NoFilesFound"
            error_message = "No files found at the specified location."
        elif num_files_checked > 0 and first_file_found is None:
            error_code = "NoMatchingFilesFound"
            error_message = "No files found at the specified location that match the provided regex filter."

    except (
        botocore.exceptions.ClientError,
        botocore.exceptions.EndpointConnectionError,
        botocore.exceptions.BotoCoreError,
    ) as e:
        error_code, error_message = _handle_boto_error(e, operation_name="list_files", raise_error=False)
    except Exception as e:
        error_code = str(e)
        error_message = str(e)
        logger.error(f"Unknown error: {error_message}")

    total_time = time.time() - start_time

    # If a file was found, get the public URL
    if first_file_found:
        assert "Key" in first_file_found, f"Key is missing from object: {first_file_found}"
        first_file_url = public_url(config, first_file_found["Key"])
    else:
        first_file_url = None

    result = ConnectionTestResult(
        connection_successful=connection_successful,
        prefix_exists=prefix_exists,
        latency=latency if latency is not None else total_time,
        total_time=total_time,
        error_message=error_message,
        error_code=error_code,
        files_checked=num_files_checked,
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
        # StreamingBody inherits from io.IOBase, but type checkers don't see that
        fp = obj.get()["Body"]
        img = PIL.Image.open(fp)  # type: ignore[arg-type]
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
        client = get_s3_client(config)
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
    client = get_s3_client(config)
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


def write_random_file(config: S3Config, key_prefix: str = "test") -> tuple[str, bytes]:
    test_key = f"{key_prefix}{random.randint(0, 99999)}.jpg"
    test_val = "".join(random.choice(string.ascii_letters) for _ in range(10)).encode("utf-8")
    obj = write_file(config, key=test_key, body=test_val)
    obj.wait_until_exists()
    return obj.key, test_val


def test():
    # boto3.set_stream_logger(name="botocore")

    config = S3Config(
        endpoint_url="http://minio:9000",
        access_key_id="minioadmin",
        secret_access_key="minioadmin",
        bucket_name="test",
        prefix="",
        public_base_url="http://minio:9000/test",
        region=None,
    )

    projects = list_projects(config)
    print("Projects:", projects)
    for project in projects:
        deployments = list_deployments(config, project)
        print("\tDeployments:", deployments)

        for deployment in deployments:
            # print("\t\tFile Count:", count_files(deployment))

            for file, _ in list_files(config, limit=1):
                if file:
                    print(file)
                    print("\t\t\tSample:", public_url(config, file.key))
