from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.utils.translation import gettext_lazy as _


class MainConfig(AppConfig):
    name = "ami.main"
    verbose_name = _("Main")

    def ready(self):
        import ami.main.signals  # noqa: F401
        from ami.tests.fixtures.signals import initialize_demo_project
        from ami.users.signals import create_global_roles, create_project_based_roles

        post_migrate.connect(initialize_demo_project, sender=self)
        post_migrate.connect(create_project_based_roles, sender=self)
        post_migrate.connect(create_global_roles, sender=self)
