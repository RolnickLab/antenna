from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MainConfig(AppConfig):
    name = "ami.exports"
    verbose_name = _("Data Exports & Reports")
