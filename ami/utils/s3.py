import io
import pathlib
from dataclasses import dataclass

import boto3
import boto3.resources.base
import botocore
import botocore.config
from mypy_boto3_s3.client import S3Client
from mypy_boto3_s3.service_resource import Bucket, S3ServiceResource

# import BucketTypeDef
from mypy_boto3_s3.type_defs import BucketTypeDef
from PIL import Image
from rich import print


@dataclass
class S3Config:
    endpoint_url: str | None
    access_key_id: str
    secret_access_key: str
    bucket_name: str
    prefix: str
    public_base_url: str = "/"


def with_trailing_slash(s: str):
    return s if s.endswith("/") else f"{s}/"


def without_trailing_slash(s: str):
    return s.rstrip("/")


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


def list_files(config: S3Config, limit: int = 10000):
    # bucket.objects.filter(Prefix=prefix).all()
    bucket = get_bucket(config)
    print(f"Scanning {bucket.name}/{config.prefix}")
    objects = bucket.objects.filter(Prefix=with_trailing_slash(config.prefix)).limit(limit).all()
    return objects


def public_url(config: S3Config, key: str):
    return f"{config.public_base_url}/{key}"


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


def resize_image(config: S3Config, key: str, width: int, height: int):
    client = get_client(config)
    new_key = resized_key(config, key, width, height)
    client.put_object(
        Bucket=config.bucket_name,
        Key=new_key,
        Body=resize_image_body(client, config.bucket_name, key, width, height),
    )
    return new_key


def resize_image_body(client: S3Client, bucket: str, key: str, width: int, height: int):
    body = client.get_object(Bucket=bucket, Key=key)["Body"].read()
    image = Image.open(io.BytesIO(body))
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
