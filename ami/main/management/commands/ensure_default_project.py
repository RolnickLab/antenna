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
import uuid

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from ami.main.models import Project

logger = logging.getLogger(__name__)

DEFAULT_PROJECT_NAME = "Default Project"
DEFAULT_COLLECTION_NAME = "Default Collection"


class Command(BaseCommand):
    help = "Idempotently create a default superuser and project for local dev / CI."

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-name",
            default=os.environ.get("ANTENNA_DEFAULT_PROJECT_NAME", DEFAULT_PROJECT_NAME),
            help="Project name to ensure exists (default: env ANTENNA_DEFAULT_PROJECT_NAME or 'Default Project')",
        )
        parser.add_argument(
            "--skip-seed",
            action="store_true",
            help="Do not seed a sample image collection (by default a small minio-backed "
            "collection is created so the minimal worker has something to process).",
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

        if not options["skip_seed"]:
            self._seed_default_collection(project)

        # Print in a stable, parseable format so shell wrappers can capture the
        # ID. Compose files can't read command output — they use env vars — so
        # the PS container reads ANTENNA_DEFAULT_PROJECT_NAME and resolves
        # to a PK via the REST API rather than relying on PK being stable.
        self.stdout.write(f"ANTENNA_DEFAULT_PROJECT_ID={project.pk}")

    def _seed_default_collection(self, project: Project) -> None:
        """Seed a small minio-backed image collection so the minimal worker has real images
        to process out of the box.

        The minimal worker opens each image and reads its pixel dimensions, so path-only
        rows won't do — the images must be reachable. This reuses the test fixtures, which
        generate images, upload them to the local object store, and sync them as captures.

        Idempotent: skips if a non-empty "Default Collection" already exists for the project
        (keyed on the collection, not on any source images — a project may have images from
        other sources but still lack the collection the worker needs). Best-effort: any failure
        (e.g. no object store in this environment) is logged and swallowed so it can never
        break the bootstrap that callers run on every startup.
        """
        from ami.main.models import SourceImageCollection

        existing = SourceImageCollection.objects.filter(project=project, name=DEFAULT_COLLECTION_NAME).first()
        if existing and existing.images.exists():
            self.stdout.write(
                f"Project '{project.name}' already has a non-empty '{DEFAULT_COLLECTION_NAME}'; skipping image seed."
            )
            return

        try:
            from ami.tests.fixtures.main import create_captures_from_files, create_deployment
            from ami.tests.fixtures.storage import create_storage_source

            short_id = uuid.uuid4().hex[:8]
            data_source = create_storage_source(project, f"Default Data Source {short_id}", prefix=short_id)
            deployment = create_deployment(project, data_source, f"Default Deployment {short_id}")
            frames = create_captures_from_files(deployment)
            images = [source_image for source_image, _frame in frames]

            collection, _ = SourceImageCollection.objects.get_or_create(project=project, name=DEFAULT_COLLECTION_NAME)
            collection.images.set(images)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Seeded {len(images)} images into '{DEFAULT_COLLECTION_NAME}' (id={collection.pk})"
                )
            )
        except Exception as e:
            logger.warning("Could not seed default image collection (continuing without it): %s", e)
            self.stdout.write(self.style.WARNING(f"Skipped image seed (continuing): {e}"))
