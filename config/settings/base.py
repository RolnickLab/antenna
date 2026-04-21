"""
Base settings to build other settings files upon.
"""

import socket
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import django_stubs_ext
import environ

# Monkeypatching Django, so stubs will work for all generics,
# see: https://github.com/typeddjango/django-stubs
django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent
# ami/
APPS_DIR = BASE_DIR / "ami"
env = environ.Env()

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=False)  # type: ignore[no-untyped-call]
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(str(BASE_DIR / ".env"))

# GENERAL
# ------------------------------------------------------------------------------
EXTERNAL_HOSTNAME = env("EXTERNAL_HOSTNAME", default="localhost:8000")  # type: ignore[no-untyped-call]
EXTERNAL_BASE_URL = env("EXTERNAL_BASE_URL", default=f"http://{EXTERNAL_HOSTNAME}")  # type: ignore[no-untyped-call]

# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = env.bool("DJANGO_DEBUG", False)  # type: ignore[no-untyped-call]
# Local time zone. Choices are
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# though not all of them may be available with every OS.
# In Windows, this must be set to your system time zone.
TIME_ZONE = "America/New_York"
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "en-us"
# https://docs.djangoproject.com/en/dev/ref/settings/#languages
# from django.utils.translation import gettext_lazy as _
# LANGUAGES = [
#     ('en', _('English')),
#     ('pt-br', _('Português')),
# ]
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1
# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = False  # All time are in local time. @TODO add timezone information to each deployment
# https://docs.djangoproject.com/en/dev/ref/settings/#locale-paths
LOCALE_PATHS = [str(BASE_DIR / "locale")]

# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
# https://docs.djangoproject.com/en/stable/ref/settings/#std:setting-DEFAULT_AUTO_FIELD
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "config.urls"
# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "config.wsgi.application"

# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.postgres",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # "django.contrib.humanize", # Handy template tags
    "django.contrib.admin",
    "django.forms",
]
THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_bootstrap5",
    "django_celery_beat",
    "rest_framework",
    "rest_framework.authtoken",
    "djoser",
    "corsheaders",
    "drf_spectacular",
    "django_filters",
    "anymail",
    "cachalot",
    "guardian",
]

LOCAL_APPS = [
    # Your stuff: custom apps go here
    "ami.users",
    "ami.main",
    "ami.jobs",
    "ami.ml",
    "ami.labelstudio",
    "ami.exports",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# MIGRATIONS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#migration-modules
MIGRATION_MODULES = {"sites": "ami.contrib.sites.migrations"}

# AUTHENTICATION
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#authentication-backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "guardian.backends.ObjectPermissionBackend",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-user-model
AUTH_USER_MODEL = "users.User"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
LOGIN_REDIRECT_URL = "users:redirect"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-url
LOGIN_URL = "login"

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = [
    # https://docs.djangoproject.com/en/dev/topics/auth/passwords/#using-argon2-with-django
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# MIDDLEWARE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# STATIC
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = str(BASE_DIR / "staticfiles")
# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/api/v2/static/"
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = [str(APPS_DIR / "static")]
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = str(APPS_DIR / "media")
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "/media/"

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # https://docs.djangoproject.com/en/dev/ref/settings/#dirs
        "DIRS": [str(APPS_DIR / "templates")],
        # https://docs.djangoproject.com/en/dev/ref/settings/#app-dirs
        "APP_DIRS": True,
        "OPTIONS": {
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

# https://docs.djangoproject.com/en/dev/ref/settings/#form-renderer
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

# http://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

# FIXTURES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#fixture-dirs
FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-httponly
SESSION_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
CSRF_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#x-frame-options
X_FRAME_OPTIONS = "DENY"

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",  # type: ignore[no-untyped-call]
)
# https://docs.djangoproject.com/en/dev/ref/settings/#email-timeout
EMAIL_TIMEOUT = 5

# Sendgrid
ANYMAIL = {
    "SENDGRID_API_KEY": env("SENDGRID_API_KEY", default=None),  # type: ignore[no-untyped-call]
}
SENDGRID_SANDBOX_MODE_IN_DEBUG = False
SENDGRID_ECHO_TO_STDOUT = True

# TCP keepalive (shared by Redis cache and Celery/RabbitMQ broker)
# ------------------------------------------------------------------------------
# Without SO_KEEPALIVE set on the client socket, the kernel never sends
# keepalive probes regardless of host-level sysctl tuning. Long-idle pooled
# connections are then vulnerable to silent drops by stateful cloud firewalls
# (the failure mode behind #1218, and the trigger for #1073).
#
# Default probe schedule: start after 60s idle, retry every 10s, give up
# after 9 failed attempts -> first dead-connection detection at ~150s.
#
# These defaults are safe for all environments: no-ops on localhost
# (local dev, docker-compose staging/demo), protective anywhere upstream
# infrastructure can drop idle connections. Production operators can
# override via env vars if their network needs different tuning (e.g. a
# more aggressive firewall might warrant a shorter idle).
TCP_KEEPALIVE_OPTIONS = {
    socket.TCP_KEEPIDLE: env.int("TCP_KEEPALIVE_IDLE", default=60),
    socket.TCP_KEEPINTVL: env.int("TCP_KEEPALIVE_INTVL", default=10),
    socket.TCP_KEEPCNT: env.int("TCP_KEEPALIVE_CNT", default=9),
}

# CACHES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#caches
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default=None),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # Mimicing memcache behavior.
            # https://github.com/jazzband/django-redis#memcached-exceptions-behavior
            "IGNORE_EXCEPTIONS": True,
            # TCP keepalive -- see TCP_KEEPALIVE_OPTIONS above.
            "SOCKET_KEEPALIVE": env.bool("REDIS_CACHE_SOCKET_KEEPALIVE", default=True),
            "SOCKET_KEEPALIVE_OPTIONS": TCP_KEEPALIVE_OPTIONS,
            # Cap connect-time to fail fast if the Redis host is unreachable,
            # rather than hanging pooled-connection acquisition indefinitely.
            # 5s is well above normal connect latency; raise in high-latency
            # networks.
            "SOCKET_CONNECT_TIMEOUT": env.int("REDIS_CACHE_SOCKET_CONNECT_TIMEOUT", default=5),
        },
    }
}
REDIS_URL = env("REDIS_URL", default=None)


# Redis DB numbering convention:
#   DB 0 = Django cache (REDIS_URL, used by django-redis CACHES above)
#   DB 1 = Celery result backend (derived automatically below)
# Separating DBs lets us flush cache without losing pending task results,
# and monitor each independently. The function below rewrites the path
# component of REDIS_URL to point at DB 1.
# TODO: consider separate Redis instances with different eviction policies:
#   allkeys-lru for cache, volatile-ttl for results. See issue #1189.
def _celery_result_backend_url(redis_url):
    if not redis_url:
        return None
    parsed = urlparse(redis_url)
    parts = [s for s in parsed.path.split("/") if s]
    if parts and parts[-1].isdigit():
        parts[-1] = "1"
    else:
        parts.append("1")
    return urlunparse(parsed._replace(path="/" + "/".join(parts)))


CELERY_RESULT_BACKEND_URL = env("CELERY_RESULT_BACKEND", default=None) or _celery_result_backend_url(REDIS_URL)

# NATS
# ------------------------------------------------------------------------------
NATS_URL = env("NATS_URL", default="nats://localhost:4222")  # type: ignore[no-untyped-call]

# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL.
ADMIN_URL = "admin/"
# https://docs.djangoproject.com/en/dev/ref/settings/#admins
ADMINS = [("""Rolnick Lab""", "michael.bunsen@mila.quebec")]
# https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
# See https://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOG_LEVEL = env.str("DJANGO_LOG_LEVEL", default="INFO").upper()  # type: ignore[no-untyped-call]
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": LOG_LEVEL,
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        }
    },
    "root": {"level": LOG_LEVEL, "handlers": ["console"]},
}

# Celery
# ------------------------------------------------------------------------------
if USE_TZ:
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-timezone
    CELERY_TIMEZONE = TIME_ZONE

CELERY_TASK_DEFAULT_QUEUE = "antenna"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-broker_url
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_backend
# Use Redis DB 1 for results (separate from cache on DB 0).
# Falls back to CELERY_RESULT_BACKEND env var if explicitly set, otherwise derives from REDIS_URL.
# See issue #1189 for discussion of result backend architecture.
CELERY_RESULT_BACKEND = CELERY_RESULT_BACKEND_URL or "rpc://"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-extended
# Stores full task args/kwargs/name in the result backend alongside status.
# Useful for: inspecting task arguments in Flower, debugging failed tasks,
# post-hoc analysis of what data a task received.
# Cost: result keys are large because process_nats_pipeline_result receives the
# full ML result JSON as args. Measured on demo (298 keys, 2026-03-26):
#   Median: 5 KB, Avg: 191 KB, Max: 2.1 MB per key
#   Distribution: 29 <1KB, 195 1-10KB, 52 100KB-1MB, 22 >1MB
# With thousands of tasks per job, this adds significant memory pressure.
# TODO: consider disabling this or setting ignore_result=True on bulk tasks
# like process_nats_pipeline_result to reduce result backend load. See #1189.
CELERY_RESULT_EXTENDED = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-always-retry
# https://github.com/celery/celery/pull/6122
CELERY_RESULT_BACKEND_ALWAYS_RETRY = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-max-retries
CELERY_RESULT_BACKEND_MAX_RETRIES = 10
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_expires
# Auto-expire task results after 72 hours. Keeps results available for inspection
# and troubleshooting while preventing unbounded growth. Override via env var (seconds).
CELERY_RESULT_EXPIRES = int(env("CELERY_RESULT_EXPIRES", default="259200"))  # type: ignore[no-untyped-call]
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-accept_content
CELERY_ACCEPT_CONTENT = ["json"]
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-task_serializer
CELERY_TASK_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_serializer
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_COMPRESSION = "gzip"
CELERY_RESULT_COMPRESSION = "gzip"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERY_TASK_TIME_LIMIT = 4 * 60 * 60 * 24  # 4 days
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-soft-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERY_TASK_SOFT_TIME_LIMIT = 3 * 60 * 60 * 24  # 3 days
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#beat-scheduler
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-send-task-events
CELERY_WORKER_SEND_TASK_EVENTS = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std-setting-task_send_sent_event
CELERY_TASK_SEND_SENT_EVENT = True

# Health checking and retries if using Redis as results backend
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#redis
CELERY_REDIS_MAX_CONNECTIONS = 50  # Total connection pool limit for results backend
CELERY_REDIS_SOCKET_TIMEOUT = 120  # Match Redis timeout
CELERY_REDIS_SOCKET_KEEPALIVE = True
CELERY_REDIS_BACKEND_HEALTH_CHECK_INTERVAL = 30  # Check health every 30s

# Help distribute long-running tasks
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-prefetch-multiplier
# @TODO Review and test this setting
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_ENABLE_PREFETCH_COUNT_REDUCTION = True

# Split Celery work across three queues so one class of task can't starve
# another. Staging/production/worker compose files each run a dedicated
# worker service per queue; local/CI use a single worker consuming all queues.
# See docker-compose.*.yml. Tasks not listed here fall back to the default
# queue (antenna).
#
#   antenna     — default: beat tasks, cache refreshes, sync jobs, misc housekeeping
#   jobs        — long-running run_job invocations (can hold a slot for hours)
#   ml_results  — high-volume process_nats_pipeline_result + save_results bursts,
#                 plus create_detection_images (emitted from save_results)
CELERY_TASK_ROUTES = {
    "ami.jobs.tasks.run_job": {"queue": "jobs"},
    "ami.jobs.tasks.process_nats_pipeline_result": {"queue": "ml_results"},
    "ami.ml.models.pipeline.save_results": {"queue": "ml_results"},
    "ami.ml.tasks.create_detection_images": {"queue": "ml_results"},
}

# Worker concurrency (prefork pool size)
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-concurrency
# Celery's own default when unset is os.cpu_count(), which on the production
# 8-core host produced an 8-process pool that could not keep up with the antenna
# queue's DB/Redis-bound tasks (process_nats_pipeline_result, create_detection_images).
# 8 is a conservative default that keeps local/staging/demo memory footprints
# reasonable (each prefork worker is a separate Python process with imports +
# DB connection). Production should override to 16 (see .envs/.production/.django-example).
CELERY_WORKER_CONCURRENCY = env.int("CELERY_WORKER_CONCURRENCY", default=8)

# Cancel & return to queue if connection is lost
# https://docs.celeryq.dev/en/latest/userguide/configuration.html#worker-cancel-long-running-tasks-on-connection-loss
CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS = True

# RabbitMQ broker connection settings
# These settings improve reliability for long-running workers with intermittent network issues
CELERY_BROKER_TRANSPORT_OPTIONS = {
    # TCP keepalive so the network stack doesn't silently drop connections.
    # Shared schedule with the Redis cache above -- see TCP_KEEPALIVE_OPTIONS.
    "socket_keepalive": True,
    "socket_settings": TCP_KEEPALIVE_OPTIONS,
    # Connection Stability Settings
    "socket_connect_timeout": 40,  # Max time to establish connection
    "retry_on_timeout": True,  # Retry operations if they time out
    "max_connections": 20,  # Connection pool limit per process
    "heartbeat": 30,  # RabbitMQ heartbeat interval (seconds) - detects broken connections
    # REMOVED "socket_timeout: 120" to prevent workers self-destructing during long blocking operations.
}

# Broker connection retry settings
# Workers will retry forever on connection failures rather than crashing
CELERY_BROKER_CONNECTION_RETRY = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_MAX_RETRIES = None  # Retry forever


# Maximum in-memory request body size for multipart form data and request.body access.
# ML detection+classification payloads for a single batch can exceed the Django
# default (2.5 MB). Configurable via env (integer, binary MiB — multiplied by
# 1024*1024) so operators can tune without a code change. See RolnickLab/antenna#1223
# for the longer-term fix (worker-side incremental result posting).
#
# Note: this setting does NOT apply to DRF JSON bodies — DRF parsers read from the
# raw WSGI stream, bypassing request.body where Django enforces this limit.
# nginx client_max_body_size is the hard cap for all request types.
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int("DJANGO_DATA_UPLOAD_MAX_MEMORY_MB", default=100) * 1024 * 1024

# django-rest-framework
# -------------------------------------------------------------------------------
# django-rest-framework - https://www.django-rest-framework.org/api-guide/settings/
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("ami.base.permissions.IsActiveStaffOrReadOnly",),
    # "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "ami.base.pagination.LimitOffsetPaginationWithPermissions",
    "PAGE_SIZE": 10,
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "HTML_SELECT_CUTOFF": 100,
}

# django-cors-headers - https://github.com/adamchainz/django-cors-headers#setup
CORS_URLS_REGEX = r"^/api/.*$"

CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=[
        "https://api.dev.insectai.org",
        "http://api.dev.insectai.org",
        EXTERNAL_BASE_URL,
    ],  # type: ignore[no-untyped-call]
)

# User authentication and registration via REST API endpoints
# https://djoser.readthedocs.io/en/latest/settings.html
DJOSER = {
    "PASSWORD_RESET_CONFIRM_URL": "auth/reset-password-confirm?uid={uid}&token={token}",
    "USERNAME_RESET_CONFIRM_URL": "#/username/reset/confirm/{uid}/{token}",
    # "ACTIVATION_URL": "#/activate/{uid}/{token}",
    "SEND_CONFIRMATION_EMAIL": True,
    # "SEND_ACTIVATION_EMAIL": True,
    "LOGIN_FIELD": "email",  # Technically not needed because we have a custom User model
    "SERIALIZERS": {
        "user": "ami.users.api.serializers.UserSerializer",
        "current_user": "ami.users.api.serializers.CurrentUserSerializer",
    },
    "PERMISSIONS": {
        "user_create": ["rest_framework.permissions.IsAdminUser"],
    },
}
# Django Guardian
ANONYMOUS_USER_NAME = "anonymoususer"

# By Default swagger ui is available only to admin user(s). You can change permission classes to change that
# See more configuration options at https://drf-spectacular.readthedocs.io/en/latest/settings.html#settings
SPECTACULAR_SETTINGS = {
    "TITLE": "Automated Monitoring of Insects ML Platform API",
    "DESCRIPTION": "Documentation of API endpoints of Automated Monitoring of Insects ML Platform",
    "VERSION": "1.0.0",
    # "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
}
# Your stuff...
# ------------------------------------------------------------------------------

DEFAULT_CONFIDENCE_THRESHOLD = env.float("DEFAULT_CONFIDENCE_THRESHOLD", default=0.6)  # type: ignore[no-untyped-call]

S3_TEST_ENDPOINT = env("MINIO_ENDPOINT", default="http://minio:9000")  # type: ignore[no-untyped-call]
S3_TEST_KEY = env("MINIO_ROOT_USER", default=None)  # type: ignore[no-untyped-call]
S3_TEST_SECRET = env("MINIO_ROOT_PASSWORD", default=None)  # type: ignore[no-untyped-call]
S3_TEST_BUCKET = env("MINIO_TEST_BUCKET", default="ami-test")  # type: ignore[no-untyped-call]
S3_TEST_REGION = env("MINIO_REGION", default=None)  # type: ignore[no-untyped-call]


# Default processing service settings
# If not set, we will not create a default processing service
DEFAULT_PROCESSING_SERVICE_NAME = env(
    "DEFAULT_PROCESSING_SERVICE_NAME", default="Default Processing Service"  # type: ignore[no-untyped-call]
)
DEFAULT_PROCESSING_SERVICE_ENDPOINT = env(
    "DEFAULT_PROCESSING_SERVICE_ENDPOINT", default=None  # type: ignore[no-untyped-call]
)
DEFAULT_PIPELINES_ENABLED = env.list("DEFAULT_PIPELINES_ENABLED", default=None)  # type: ignore[no-untyped-call]
# Default taxa filters
DEFAULT_INCLUDE_TAXA = env.list("DEFAULT_INCLUDE_TAXA", default=[])  # type: ignore[no-untyped-call]
DEFAULT_EXCLUDE_TAXA = env.list("DEFAULT_EXCLUDE_TAXA", default=[])  # type: ignore[no-untyped-call]

# When True, ``JobLogHandler.emit`` persists each log line to ``jobs_job.logs``
# (JSONB column) so the per-job log feed in the UI stays populated. When False,
# log lines go to the container stdout logger only — used as an escape hatch
# under concurrent async_api load where the per-record UPDATE on ``jobs_job.logs``
# becomes a row-lock contention point (see issue #1256, PR #1261). Default True
# preserves existing behavior; deployments seeing contention can set to False
# until the append-only ``JobLog`` child table (PR #1259) is in place.
JOB_LOG_PERSIST_ENABLED = env.bool("JOB_LOG_PERSIST_ENABLED", default=True)  # type: ignore[no-untyped-call]
