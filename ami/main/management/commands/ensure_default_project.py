"""
Idempotent bootstrap command for local dev and CI.

Ensures a superuser and a named Project exist so that local-dev / CI processing
services can register pipelines against Antenna without any manual setup step.

Guarded behind the ENSURE_DEFAULT_PROJECT env var so production deployments
never run it accidentally. Intended to be called from compose/local/django/start.

Looks up / creates the Project by name (no slug field on Project) so running
this in a long-lived dev DB where PK 1 is already taken by a different project
doesn't conflict.
"""

import logging
import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from ami.main.models import Project

logger = logging.getLogger(__name__)

DEFAULT_PROJECT_NAME = "Default Project"


class Command(BaseCommand):
    help = "Idempotently create a default superuser and project for local dev / CI."

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-name",
            default=os.environ.get("ANTENNA_DEFAULT_PROJECT_NAME", DEFAULT_PROJECT_NAME),
            help="Project name to ensure exists (default: env ANTENNA_DEFAULT_PROJECT_NAME or 'Default Project')",
        )

    def handle(self, *args, **options):
        User = get_user_model()

        try:
            call_command("createsuperuser", interactive=False)
            self.stdout.write(self.style.SUCCESS("Created superuser from DJANGO_SUPERUSER_* env vars"))
        except Exception as e:
            # createsuperuser raises CommandError if the user already exists;
            # that's the idempotent path we want.
            logger.info("Superuser createsuperuser call reported: %s", e)

        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        owner = User.objects.filter(email=email).first() if email else None
        if owner is None:
            self.stdout.write(
                self.style.WARNING(
                    "No DJANGO_SUPERUSER_EMAIL env var (or user not found). "
                    "Project will be created without an owner."
                )
            )

        project_name = options["project_name"]
        with transaction.atomic():
            project, created = Project.objects.get_or_create(
                name=project_name,
                defaults={"owner": owner, "description": "Bootstrap project for local dev and CI."},
            )

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created project '{project_name}' (id={project.pk})"))
        else:
            self.stdout.write(f"Project '{project_name}' already exists (id={project.pk})")

        # Print in a stable, parseable format so shell wrappers can capture the
        # ID. Compose files can't read command output — they use env vars — so
        # the PS container reads ANTENNA_DEFAULT_PROJECT_NAME and resolves
        # to a PK via the REST API rather than relying on PK being stable.
        self.stdout.write(f"ANTENNA_DEFAULT_PROJECT_ID={project.pk}")
