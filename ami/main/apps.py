from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.utils.translation import gettext_lazy as _


class MainConfig(AppConfig):
    name = "ami.main"
    verbose_name = _("Main")

    def ready(self):
        from ami.tests.fixtures.signals import setup_complete_test_project

        post_migrate.connect(setup_complete_test_project, sender=self)
