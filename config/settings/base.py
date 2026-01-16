"""
Base settings to build other settings files upon.
"""

import socket
from pathlib import Path

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
        },
    }
}
REDIS_URL = env("REDIS_URL", default=None)

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
# "rpc://" means use RabbitMQ for results backend by default
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="rpc://")  # type: ignore[no-untyped-call]
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-extended
CELERY_RESULT_EXTENDED = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-always-retry
# https://github.com/celery/celery/pull/6122
CELERY_RESULT_BACKEND_ALWAYS_RETRY = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-max-retries
CELERY_RESULT_BACKEND_MAX_RETRIES = 10
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

# Cancel & return to queue if connection is lost
# https://docs.celeryq.dev/en/latest/userguide/configuration.html#worker-cancel-long-running-tasks-on-connection-loss
CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS = True

# RabbitMQ broker connection settings
# These settings improve reliability for long-running workers with intermittent network issues
CELERY_BROKER_TRANSPORT_OPTIONS = {
    # Custom TCP Keepalives to ensure network stack doesn't silently drop connections
    "socket_keepalive": True,
    "socket_settings": {
        # Start sending Keepalive packets after 60 seconds of silence.
        # This forces traffic on the wire, preventing the OpenStack 1-hour timeout.
        socket.TCP_KEEPIDLE: 60,
        # If no response, retry every 10 seconds.
        socket.TCP_KEEPINTVL: 10,
        # Give up and close connection after 9 failed attempts.
        socket.TCP_KEEPCNT: 9,
    },
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


# Default processing service settings
# If not set, we will not create a default processing service
DEFAULT_PROCESSING_SERVICE_NAME = env(
    "DEFAULT_PROCESSING_SERVICE_NAME", default="Default Processing Service"  # type: ignore[no-untyped-call]
)
DEFAULT_PROCESSING_SERVICE_ENDPOINT = env(
    "DEFAULT_PROCESSING_SERVICE_ENDPOINT", default=None  # type: ignore[no-untyped-call]
)
DEFAULT_PIPELINES_ENABLED = env.list("DEFAULT_PIPELINES_ENABLED", default=None)  # type: ignore[no-untyped-call]
