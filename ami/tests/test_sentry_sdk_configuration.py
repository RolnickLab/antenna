import importlib
import sys

import sentry_sdk


def test_production_settings_initializes_sentry_from_environment(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "example.com,api.example.com")
    monkeypatch.setenv("DJANGO_AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("DJANGO_AWS_SECRET_ACCESS_KEY", "testing-secret")
    monkeypatch.setenv("DJANGO_AWS_STORAGE_BUCKET_NAME", "antenna-tests")
    monkeypatch.setenv("DJANGO_ADMIN_URL", "admin/")
    monkeypatch.setenv("SENDGRID_API_KEY", "sendgrid-key")
    monkeypatch.setenv("SENTRY_DSN", "https://public@example.ingest.sentry.io/1")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "staging")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.5")
    monkeypatch.setenv("SENTRY_PROFILES_SAMPLE_RATE", "0.01")

    init_calls = []

    def fake_init(**kwargs):
        init_calls.append(kwargs)

    monkeypatch.setattr(sentry_sdk, "init", fake_init)
    sys.modules.pop("config.settings.production", None)

    try:
        importlib.import_module("config.settings.production")
    finally:
        sys.modules.pop("config.settings.production", None)

    assert len(init_calls) == 1

    init_kwargs = init_calls[0]
    assert init_kwargs["dsn"] == "https://public@example.ingest.sentry.io/1"
    assert init_kwargs["environment"] == "staging"
    assert init_kwargs["traces_sample_rate"] == 0.5
    assert init_kwargs["profiles_sample_rate"] == 0.01
    assert len(init_kwargs["integrations"]) == 4
