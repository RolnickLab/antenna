
"""
Manages application secrets and configuration.
Creates AWS Secrets Manager entries, derives database/Redis URLs,
and exports Elastic Beanstalk environment variables.
"""



import json
import urllib.parse

import pulumi
import pulumi_aws as aws

from antennav2_rds import rds_instance
from antennav2_redis import redis, REDIS_PORT

config = pulumi.Config()
STACK = pulumi.get_stack()
PROJECT = pulumi.get_project()


# =========================================================
# Helper: create Secrets Manager secret + version
# =========================================================
def create_secret(
    key: str,
    value: pulumi.Input[str],
    description: str = "",
) -> aws.secretsmanager.Secret:
    secret_name = f"{PROJECT}-{STACK}-{key}"

    secret = aws.secretsmanager.Secret(
        secret_name,
        name=secret_name,
        description=description or f"Managed by Pulumi: {secret_name}",
        tags={
            "Name": secret_name,
            "ManagedBy": "Pulumi",
            "Project": "Antenna",
            "PulumiProject": PROJECT,
            "PulumiStack": STACK,
        },
    )

    aws.secretsmanager.SecretVersion(
        f"{secret_name}-version",
        secret_id=secret.id,
        secret_string=value,
    )

    pulumi.export(f"{key}_SECRET_ARN", secret.arn)
    return secret


# =========================================================
# TRUE SECRETS (Pulumi encrypted secrets)
# =========================================================

DJANGO_SECRET_KEY_secret = create_secret(
    "DJANGO_SECRET_KEY",
    config.require_secret("DJANGO_SECRET_KEY"),
    "Django secret key",
)

SENDGRID_API_KEY_secret = create_secret(
    "SENDGRID_API_KEY",
    config.require_secret("SENDGRID_API_KEY"),
    "SendGrid API key",
)

SENTRY_DSN_secret = create_secret(
    "SENTRY_DSN",
    config.require_secret("SENTRY_DSN"),
    "Sentry DSN",
)

# =========================================================
# S3 CREDENTIALS (Pulumi encrypted secrets)
# =========================================================

DJANGO_AWS_ACCESS_KEY_ID_secret = create_secret(
    "DJANGO_AWS_ACCESS_KEY_ID",
    config.require_secret("DJANGO_AWS_ACCESS_KEY_ID"),
    "AWS access key id for django S3 storage",
)

DJANGO_AWS_SECRET_ACCESS_KEY_secret = create_secret(
    "DJANGO_AWS_SECRET_ACCESS_KEY",
    config.require_secret("DJANGO_AWS_SECRET_ACCESS_KEY"),
    "AWS secret access key for django S3 storage",
)

# =========================================================
# DERIVED SECRETS (Redis / Celery URLs)
# =========================================================

REDIS_URL = redis.primary_endpoint_address.apply(
    lambda host: f"rediss://{host}:{REDIS_PORT}/0?ssl_cert_reqs=none"
)

CELERY_BROKER_URL = redis.primary_endpoint_address.apply(
    lambda host: f"rediss://{host}:{REDIS_PORT}/0?ssl_cert_reqs=none"
)

REDIS_URL_secret = create_secret(
    "REDIS_URL",
    REDIS_URL,
    "Redis URL for Django/Celery (TLS)",
)

CELERY_BROKER_URL_secret = create_secret(
    "CELERY_BROKER_URL",
    CELERY_BROKER_URL,
    "Celery broker URL (TLS)",
)

# =========================================================
# Postgres config
# =========================================================

POSTGRES_PASSWORD_PULUMI = config.require_secret("POSTGRES_PASSWORD")
POSTGRES_USER = config.require("POSTGRES_USER")

# =========================================================
# NON-SECRET CONFIG (needed by runtime)
# =========================================================

DJANGO_SETTINGS_MODULE = config.require("DJANGO_SETTINGS_MODULE")
DJANGO_DEBUG = config.require("DJANGO_DEBUG")
DJANGO_ALLOWED_HOSTS = config.require("DJANGO_ALLOWED_HOSTS")
DJANGO_SECURE_SSL_REDIRECT = config.require("DJANGO_SECURE_SSL_REDIRECT")
DJANGO_ADMIN_URL = config.require("DJANGO_ADMIN_URL")

POSTGRES_DB = config.require("POSTGRES_DB")
POSTGRES_PORT = config.require("POSTGRES_PORT")

DEFAULT_PROCESSING_SERVICE_ENDPOINT = config.require("DEFAULT_PROCESSING_SERVICE_ENDPOINT")
EB_HEALTHCHECK = config.require("EB_HEALTHCHECK")

DJANGO_AWS_STORAGE_BUCKET_NAME = config.require("DJANGO_AWS_STORAGE_BUCKET_NAME")
DJANGO_AWS_S3_REGION_NAME = config.require("DJANGO_AWS_S3_REGION_NAME")

# Derived non-secret
POSTGRES_HOST = rds_instance.address

# =========================================================
# Secrets we inject into containers
# =========================================================

POSTGRES_PASSWORD_secret = create_secret(
    "POSTGRES_PASSWORD",
    POSTGRES_PASSWORD_PULUMI,
    "Postgres password",
)

# =========================================================
# DERIVED DATABASE_URL SECRET (URL-encoded password)
# =========================================================

DATABASE_URL = pulumi.Output.all(
    POSTGRES_USER,
    POSTGRES_PASSWORD_PULUMI,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
).apply(
    lambda args: (
        "postgres://"
        f"{args[0]}:{urllib.parse.quote(args[1])}"
        f"@{args[2]}:{args[3]}/{args[4]}"
    )
)

DATABASE_URL_secret = create_secret(
    "DATABASE_URL",
    DATABASE_URL,
    "Full Postgres connection URL for Django",
)

# =========================================================
# EB ENV (console-visible only)
# =========================================================

EB_ENV = {
    # Django (plain)
    "DJANGO_SETTINGS_MODULE": DJANGO_SETTINGS_MODULE,
    "DJANGO_DEBUG": DJANGO_DEBUG,
    "DJANGO_ALLOWED_HOSTS": DJANGO_ALLOWED_HOSTS,
    "DJANGO_SECURE_SSL_REDIRECT": DJANGO_SECURE_SSL_REDIRECT,
    "DJANGO_ADMIN_URL": DJANGO_ADMIN_URL,

    # Postgres pieces (plain)
    "POSTGRES_HOST": POSTGRES_HOST,
    "POSTGRES_PORT": POSTGRES_PORT,
    "POSTGRES_DB": POSTGRES_DB,
    "POSTGRES_USER": POSTGRES_USER,

    # Force SSL
    "PGSSLMODE": "require",

    # App config (plain)
    "DEFAULT_PROCESSING_SERVICE_ENDPOINT": DEFAULT_PROCESSING_SERVICE_ENDPOINT,
    "EB_HEALTHCHECK": EB_HEALTHCHECK,

    # S3 (plain)
    "DJANGO_AWS_STORAGE_BUCKET_NAME": DJANGO_AWS_STORAGE_BUCKET_NAME,
    "DJANGO_AWS_S3_REGION_NAME": DJANGO_AWS_S3_REGION_NAME,

    # Secret ARNs
    "DJANGO_SECRET_KEY_SECRET_ARN": DJANGO_SECRET_KEY_secret.arn,
    "POSTGRES_PASSWORD_SECRET_ARN": POSTGRES_PASSWORD_secret.arn,
    "DATABASE_URL_SECRET_ARN": DATABASE_URL_secret.arn,
    "SENDGRID_API_KEY_SECRET_ARN": SENDGRID_API_KEY_secret.arn,
    "SENTRY_DSN_SECRET_ARN": SENTRY_DSN_secret.arn,
    "REDIS_URL_SECRET_ARN": REDIS_URL_secret.arn,
    "CELERY_BROKER_URL_SECRET_ARN": CELERY_BROKER_URL_secret.arn,

    # S3 credential secrets
    "DJANGO_AWS_ACCESS_KEY_ID_SECRET_ARN": DJANGO_AWS_ACCESS_KEY_ID_secret.arn,
    "DJANGO_AWS_SECRET_ACCESS_KEY_SECRET_ARN": DJANGO_AWS_SECRET_ACCESS_KEY_secret.arn,
}

pulumi.export("EB_ENV", EB_ENV)
