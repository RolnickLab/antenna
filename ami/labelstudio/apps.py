from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class LabelStudioConfig(AppConfig):
    name = "ami.labelstudio"
    verbose_name = _("Label Studio Integration")
