from django.apps import AppConfig


class ExportsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ami.exports"

    def ready(self):
        import ami.exports.signals  # noqa: F401
