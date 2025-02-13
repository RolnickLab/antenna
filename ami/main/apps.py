from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.utils.translation import gettext_lazy as _


class MainConfig(AppConfig):
    name = "ami.main"
    verbose_name = _("Main")

    def ready(self):
        import ami.main.signals  # noqa: F401
        from ami.tests.fixtures.signals import initialize_demo_project

        post_migrate.connect(initialize_demo_project, sender=self)
