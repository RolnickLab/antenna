from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MLConfig(AppConfig):
    name = "ami.ml"
    verbose_name = _("Machine Learning")

    def ready(self):
        import ami.ml.signals  # noqa: F401
