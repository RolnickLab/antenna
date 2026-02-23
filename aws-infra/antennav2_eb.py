"""
Creates and deploys the Elastic Beanstalk environment.

Builds the Dockerrun bundle, uploads it to S3,
and provisions the EB app, version, and environment.
"""





import os
import json
import zipfile
import hashlib

import pulumi
import pulumi_aws as aws

from pulumi import ResourceOptions, CustomTimeouts

config = pulumi.Config()

flower_config = pulumi.Config("flower")

flower_user = flower_config.get("user")
flower_password = flower_config.get("password")


# ---------------------------------------------------------
# ECR repos + docker build/push
# ---------------------------------------------------------
import antennav2_ecr
import antennav2_images
import antennav2_redis


# ---------------------------------------------------------
# IAM roles + networking
# ---------------------------------------------------------
from antennav2_iam_roles import (
    ec2_instance_profile_pulumi,
    service_role_pulumi,
    ecs_execution_role,
    eb_ec2_passrole_ecs_execution,
)
from networking.antennav2_subnets import private_redis_subnets

from networking.antennav2_security_group import eb_sg

# ---------------------------------------------------------
# Infra outputs
# ---------------------------------------------------------
from antennav2_rds import rds_instance
from antennav2_redis import redis

# ---------------------------------------------------------
# EB_ENV contains:
#   - plain env vars
#   - *_SECRET_ARN pointers used to populate Dockerrun "secrets"
# ---------------------------------------------------------
from antennav2_secrets_manager import EB_ENV

# ---------------------------------------------------------
# Constants
# ---------------------------------------------------------
BUILD_DIR = "build_eb_bundle"
DOCKERRUN_PATH = os.path.join(BUILD_DIR, "Dockerrun.aws.json")
DEPLOY_ZIP_PATH = os.path.join(BUILD_DIR, "deploy.zip")


BACKEND_TAG = "backend"
AWSCLI_TAG = "awscli"
ML_MIN_TAG = "ml-minimal"
ML_EX_TAG = "ml-example"


def ensure_build_dir() -> None:
    os.makedirs(BUILD_DIR, exist_ok=True)


def _split_plain_env_and_secret_arns(env: dict) -> tuple[list[dict], dict]:
    """
    EB_ENV contains:
      - plain env vars (strings)
      - secret ARN pointers (keys ending with _SECRET_ARN)

    We generate:
      - "environment": list[{name,value}] for plain vars
      - "secrets": list[{name,valueFrom}] for secret values
        (container gets env var NAME with secret VALUE at runtime)
    """
    plain_env_list: list[dict] = []
    secret_arns: dict[str, str] = {}

    for k, v in env.items():
        if k.endswith("_SECRET_ARN"):
            secret_arns[k] = v
            continue

        plain_env_list.append({"name": k, "value": v})

    return plain_env_list, secret_arns


def _require_secret_arn(secret_arns: dict[str, str], key: str) -> str:
    """
    Fail early with a message if a required *_SECRET_ARN entry is missing.
    """
    if key not in secret_arns or not secret_arns[key]:
        raise Exception(f"Missing required secret ARN in EB_ENV: {key}")
    return secret_arns[key]


def build_dockerrun_and_zip(
    backend_repo_url: str,
    awscli_repo_url: str,
    mlmin_repo_url: str,
    mlex_repo_url: str,
    execution_role_arn: str,
    postgres_host: str,
    eb_env: dict,
) -> str:
    """
    Generate Dockerrun.aws.json (AWSEBDockerrunVersion 2)
    and zip it into deploy.zip with Dockerrun at ZIP ROOT.
    """
    ensure_build_dir()

    backend_image = f"{backend_repo_url}:{BACKEND_TAG}"
    awscli_image = f"{awscli_repo_url}:{AWSCLI_TAG}"
    ml_min_image = f"{mlmin_repo_url}:{ML_MIN_TAG}"
    ml_ex_image = f"{mlex_repo_url}:{ML_EX_TAG}"

    # Split EB_ENV into plain vars vs secret ARN pointers
    plain_env_list, secret_arns = _split_plain_env_and_secret_arns(eb_env)

    # Force POSTGRES_HOST from RDS output so it's always correct/reliable
    plain_env_list = [e for e in plain_env_list if e["name"] != "POSTGRES_HOST"]
    plain_env_list.append({"name": "POSTGRES_HOST", "value": postgres_host})

    # Force SSL for postgres clients
    plain_env_list = [e for e in plain_env_list if e["name"] != "PGSSLMODE"]
    plain_env_list.append({"name": "PGSSLMODE", "value": "require"})

    # Shared runtime env for all backend containers (django/celery/flower)
    backend_environment = [{"name": "USE_DOCKER", "value": "yes"}] + plain_env_list

    # ECS secrets injection:
    # valueFrom MUST be secret ARN; "name" becomes the env var in the container.
    backend_secrets: list[dict] = [
        {"name": "DJANGO_SECRET_KEY", "valueFrom": _require_secret_arn(secret_arns, "DJANGO_SECRET_KEY_SECRET_ARN")},
        {"name": "POSTGRES_PASSWORD", "valueFrom": _require_secret_arn(secret_arns, "POSTGRES_PASSWORD_SECRET_ARN")},
        {"name": "DATABASE_URL", "valueFrom": _require_secret_arn(secret_arns, "DATABASE_URL_SECRET_ARN")},
    ]

    # S3 credentials
    backend_secrets += [
        {"name": "DJANGO_AWS_ACCESS_KEY_ID", "valueFrom": _require_secret_arn(secret_arns, "DJANGO_AWS_ACCESS_KEY_ID_SECRET_ARN")},
        {"name": "DJANGO_AWS_SECRET_ACCESS_KEY", "valueFrom": _require_secret_arn(secret_arns, "DJANGO_AWS_SECRET_ACCESS_KEY_SECRET_ARN")},
    ]

    # Other secrets
    backend_secrets += [
        {"name": "SENDGRID_API_KEY", "valueFrom": _require_secret_arn(secret_arns, "SENDGRID_API_KEY_SECRET_ARN")},
        {"name": "SENTRY_DSN", "valueFrom": _require_secret_arn(secret_arns, "SENTRY_DSN_SECRET_ARN")},
        {"name": "REDIS_URL", "valueFrom": _require_secret_arn(secret_arns, "REDIS_URL_SECRET_ARN")},
        {"name": "CELERY_BROKER_URL", "valueFrom": _require_secret_arn(secret_arns, "CELERY_BROKER_URL_SECRET_ARN")},
    ]

    dockerrun = {
        "AWSEBDockerrunVersion": 2,
        "executionRoleArn": execution_role_arn,
        "containerDefinitions": [
            {
                "name": "ml-backend-minimal",
                "image": ml_min_image,
                "essential": False,
                "memory": 512,
                "hostname": "ml-backend-minimal",
                "portMappings": [{"hostPort": 2000, "containerPort": 2000}],
            },
            {
                "name": "ml-backend-example",
                "image": ml_ex_image,
                "essential": False,
                "memory": 512,
                "hostname": "ml-backend-example",
                "portMappings": [{"hostPort": 2003, "containerPort": 2000}],
            },
            {
                "name": "awscli",
                "image": awscli_image,
                "essential": False,
                "memory": 256,
                "command": ["sleep", "9999999"],
                "environment": [{"name": "AWS_REGION", "value": aws.config.region}],
            },
            {
                "name": "django",
                "image": backend_image,
                "essential": True,
                "memory": 1024,
                "entryPoint": ["/entrypoint"],
                "portMappings": [{"hostPort": 80, "containerPort": 5000}],
                "command": ["/start"],
                "environment": backend_environment + [
                    {"name": "DEFAULT_PROCESSING_SERVICE_ENDPOINT", "value": "http://ml-backend-minimal:2000"},
                    {"name": "DEFAULT_PROCESSING_SERVICE_NAME", "value": "Default ML Service"},
                ],
                "links": ["ml-backend-minimal", "ml-backend-example"],
                "secrets": backend_secrets,
                "dependsOn": [
                    {"containerName": "ml-backend-minimal", "condition": "START"},
                    {"containerName": "ml-backend-example", "condition": "START"},
                ],
            },
            {
                "name": "celeryworker",
                "image": backend_image,
                "essential": False,
                "memory": 512,
                "entryPoint": ["/entrypoint"],
                "command": ["/start-celeryworker"],
                "environment": backend_environment + [
                    {"name": "DEFAULT_PROCESSING_SERVICE_ENDPOINT", "value": "http://ml-backend-minimal:2000"},
                ],
                "links": ["ml-backend-minimal", "ml-backend-example"],
                "secrets": backend_secrets,
                "dependsOn": [{"containerName": "django", "condition": "START"}],
            },
            {
                "name": "celerybeat",
                "image": backend_image,
                "essential": False,
                "memory": 512,
                "entryPoint": ["/entrypoint"],
                "command": ["/start-celerybeat"],
                "environment": backend_environment + [
                    {"name": "DEFAULT_PROCESSING_SERVICE_ENDPOINT", "value": "http://ml-backend-minimal:2000"},
                ],
                "links": ["ml-backend-minimal", "ml-backend-example"],
                "secrets": backend_secrets,
                "dependsOn": [{"containerName": "django", "condition": "START"}],
            },
            {
                "name": "flower",
                "image": backend_image,
                "essential": False,
                "memory": 512,
                "entryPoint": ["/entrypoint"],
                "portMappings": [{"hostPort": 5555, "containerPort": 5555}],
                "command": ["/start-flower"],
                "environment": backend_environment + [
                    {"name": "CELERY_FLOWER_USER", "value": flower_user},
                    {"name": "CELERY_FLOWER_PASSWORD", "value": flower_password},
                    {"name": "DEFAULT_PROCESSING_SERVICE_ENDPOINT", "value": "http://ml-backend-minimal:2000"},
                ],
                "links": ["ml-backend-minimal", "ml-backend-example"],
                "secrets": backend_secrets,
                "dependsOn": [{"containerName": "django", "condition": "START"}],
            },
        ],
    }

    with open(DOCKERRUN_PATH, "w") as f:
        json.dump(dockerrun, f, indent=2)

    if os.path.exists(DEPLOY_ZIP_PATH):
        os.remove(DEPLOY_ZIP_PATH)

    with zipfile.ZipFile(DEPLOY_ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(DOCKERRUN_PATH, arcname="Dockerrun.aws.json")

    return DEPLOY_ZIP_PATH


def file_sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def make_bundle_key_and_asset(zip_path: str):
    sha = file_sha256(zip_path)
    return sha, f"deploy-{sha}.zip", pulumi.FileAsset(zip_path)


# ---------------------------------------------------------
# 1) Create deploy bundle
# ---------------------------------------------------------

zip_meta_output = (
    pulumi.Output.all(
        antennav2_ecr.ecr_repos["antenna-pulumi"].repository_url,
        antennav2_ecr.ecr_repos["antenna-pulumi"].repository_url,
        antennav2_ecr.ecr_repos["antenna-pulumi"].repository_url,
        antennav2_ecr.ecr_repos["antenna-pulumi"].repository_url,
        ecs_execution_role.arn,
        rds_instance.address,  # authoritative POSTGRES_HOST
        EB_ENV,                # contains both plain vars and secret ARN pointers
    )
    .apply(lambda args: build_dockerrun_and_zip(*args))
    .apply(make_bundle_key_and_asset)
)


# ---------------------------------------------------------
# 2) EB prereqs
# ---------------------------------------------------------
default_vpc = aws.ec2.get_vpc_output(default=True)

solution_stack_regex = config.get(
    "EB_SOLUTION_STACK_REGEX"
)

ecs_solution_stack = aws.elasticbeanstalk.get_solution_stack(
    name_regex=solution_stack_regex,
    most_recent=True,
)

# ---------------------------------------------------------
# 3) EB Application
# ---------------------------------------------------------
eb_app_pulumi = aws.elasticbeanstalk.Application(
    "antenna-django-eb-app-pulumi",
    name="antenna-django-eb-app-pulumi",
)

# ---------------------------------------------------------
# 4) S3 bundle bucket + object
# ---------------------------------------------------------


# force_destroy=True is intentional for dev/CI to allow clean stack teardown.
# We’ll disable this in production.

eb_bundle_bucket = aws.s3.Bucket(
    "antenna-eb-bundles-pulumi",
    force_destroy=True,
)

eb_bundle_object = aws.s3.BucketObject(
    "antenna-eb-deploy-zip",
    bucket=eb_bundle_bucket.bucket,
    key=zip_meta_output.apply(lambda x: x[1]),
    source=zip_meta_output.apply(lambda x: x[2]),
)

# ---------------------------------------------------------
# 5) EB Application Version
# ---------------------------------------------------------
app_version = aws.elasticbeanstalk.ApplicationVersion(
    "antenna-eb-app-version-pulumi",
    application=eb_app_pulumi.name,
    bucket=eb_bundle_bucket.bucket,
    key=eb_bundle_object.key,
    name=zip_meta_output.apply(lambda x: f"deploy-{x[0]}"),
)

# ---------------------------------------------------------
# 6) EB Environment Settings
# NOTE: console visibility only.
# IMPORTANT: do NOT inject *_SECRET_ARN keys here.
# ---------------------------------------------------------
eb_console_env = {k: v for k, v in EB_ENV.items() if not k.endswith("_SECRET_ARN")}

eb_app_env_settings = [
    aws.elasticbeanstalk.EnvironmentSettingArgs(
        namespace="aws:elasticbeanstalk:application:environment",
        name=k,
        value=v,
    )
    for k, v in eb_console_env.items()
]


# (POSTGRES_HOST is already in eb_console_env after filtering secrets, but we keep this override
#  to ensure the RDS output wins if anything drifted.)
eb_app_env_settings += [
    aws.elasticbeanstalk.EnvironmentSettingArgs(
        namespace="aws:elasticbeanstalk:application:environment",
        name="POSTGRES_HOST",
        value=rds_instance.address,
    ),
    aws.elasticbeanstalk.EnvironmentSettingArgs(
        namespace="aws:elasticbeanstalk:application:environment",
        name="REDIS_HOST",
        value = antennav2_redis.redis.primary_endpoint_address,

    ),
]

eb_env_settings = [
    aws.elasticbeanstalk.EnvironmentSettingArgs(namespace="aws:ec2:vpc", name="VPCId", value=default_vpc.id),
    aws.elasticbeanstalk.EnvironmentSettingArgs(namespace="aws:ec2:vpc", name="AssociatePublicIpAddress", value="true"),
    aws.elasticbeanstalk.EnvironmentSettingArgs(
        namespace="aws:ec2:vpc",
        name="Subnets",
        value=pulumi.Output.all(*[s.id for s in private_redis_subnets]).apply(",".join),
    ),
    aws.elasticbeanstalk.EnvironmentSettingArgs(
        namespace="aws:elasticbeanstalk:environment",
        name="EnvironmentType",
        value="SingleInstance",
    ),
    aws.elasticbeanstalk.EnvironmentSettingArgs(
        namespace="aws:autoscaling:launchconfiguration",
        name="InstanceType",
        value="t3.large",
    ),
    aws.elasticbeanstalk.EnvironmentSettingArgs(
        namespace="aws:autoscaling:launchconfiguration",
        name="SecurityGroups",
        value=eb_sg.id,
    ),
    aws.elasticbeanstalk.EnvironmentSettingArgs(
        namespace="aws:autoscaling:launchconfiguration",
        name="RootVolumeSize",
        value="30",
    ),
    aws.elasticbeanstalk.EnvironmentSettingArgs(
        namespace="aws:autoscaling:launchconfiguration",
        name="IamInstanceProfile",
        value=ec2_instance_profile_pulumi.name,
    ),
    aws.elasticbeanstalk.EnvironmentSettingArgs(
        namespace="aws:elasticbeanstalk:environment",
        name="ServiceRole",
        value=service_role_pulumi.name,
    ),
]

eb_env_settings += eb_app_env_settings

# ---------------------------------------------------------
# 7) EB Environment
# ---------------------------------------------------------
env_pulumi = aws.elasticbeanstalk.Environment(
    "antenna-django-eb-env-pulumi-v2",
    application=eb_app_pulumi.name,
    solution_stack_name=ecs_solution_stack.name,
    version=app_version.name,
    settings=eb_env_settings,
    opts=pulumi.ResourceOptions(
        depends_on=[
            ecs_execution_role,
            eb_ec2_passrole_ecs_execution,
            app_version,
            antennav2_images.backend_image,
            antennav2_images.awscli_image,
            antennav2_images.ml_min_image,
            antennav2_images.ml_ex_image,
        ],

        custom_timeouts=CustomTimeouts(create="60m", update="60m"),
    ),
)

# ---------------------------------------------------------
# 8) Outputs
# ---------------------------------------------------------
pulumi.export("eb_env_name_pulumi", env_pulumi.name)
pulumi.export("eb_url_pulumi", env_pulumi.endpoint_url)
pulumi.export("eb_bundle_bucket", eb_bundle_bucket.bucket)
pulumi.export("eb_deploy_zip_s3_key", eb_bundle_object.key)
pulumi.export("eb_deploy_version_label", app_version.name)
