"""Generate a project taxa list from a geographic region (issue #1364).

A thin wrapper over `ami.main.services.regional_taxa.generate_regional_taxa_list`. Run
it for one project with an explicit region, or use `--all-projects` to backfill every
project, deriving each one's region from a representative deployment's coordinates
(GBIF reverse-geocode). The heavy lifting lives in the service so the same behavior is
reachable from the admin, the API, and tests; this command is the operator/backfill
entry point.
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand, CommandError

from ami.main.models import Project, RegionSource
from ami.main.services import regional_taxa

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate a project taxa list from a geographic region (GBIF/GADM)."

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, help="Project id to attach the list to.")
        parser.add_argument(
            "--all-projects",
            action="store_true",
            help="Backfill every project, deriving each region from its deployments.",
        )
        parser.add_argument(
            "--region-source",
            default=RegionSource.GBIF_GADM.value,
            choices=[choice.value for choice in RegionSource],
        )
        parser.add_argument(
            "--region-code",
            help="Region id (a GADM gid such as USA.46_1). Omit with --all-projects; it is derived.",
        )
        parser.add_argument("--classifier", type=int, help="Algorithm id for a reporting-only coverage overlay.")
        parser.add_argument("--name", help="TaxaList name (defaults to the region code).")
        parser.add_argument(
            "--include-uncovered",
            action="store_true",
            help="Also keep regional species no model can predict (each flagged as uncovered).",
        )
        parser.add_argument(
            "--no-create-missing",
            action="store_true",
            help="Do not create Taxon rows for regional species absent from the database.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Report the counts without writing anything.")

    def handle(self, *args, **options):
        classifier = self._resolve_classifier(options.get("classifier"))
        common = dict(
            region_source=options["region_source"],
            classifier=classifier,
            include_uncovered=options["include_uncovered"],
            create_missing=not options["no_create_missing"],
            name=options["name"],
            dry_run=options["dry_run"],
        )

        if options["all_projects"]:
            if options["region_code"]:
                raise CommandError("--region-code is derived per project with --all-projects; do not pass it.")
            self._run_all_projects(common)
            return

        if not options["region_code"]:
            raise CommandError("--region-code is required unless --all-projects is used.")
        project = self._resolve_project(options.get("project"))
        result = regional_taxa.generate_regional_taxa_list(
            project=project, region_code=options["region_code"], **common
        )
        self._report(project, result)

    def _run_all_projects(self, common: dict) -> None:
        for project in Project.objects.all().order_by("pk"):
            derived = regional_taxa.derive_region_for_project(project, region_source=common["region_source"])
            if derived is None:
                self.stdout.write(f"[skip] project {project.pk} {project.name!r}: no region could be derived")
                continue
            _source, region_code = derived
            result = regional_taxa.generate_regional_taxa_list(project=project, region_code=region_code, **common)
            self._report(project, result)

    def _resolve_project(self, project_id: int | None) -> Project | None:
        if not project_id:
            return None
        try:
            return Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            raise CommandError(f"Project {project_id} does not exist.")

    def _resolve_classifier(self, classifier_id: int | None):
        if not classifier_id:
            return None
        from ami.ml.models.algorithm import Algorithm

        try:
            return Algorithm.objects.get(pk=classifier_id)
        except Algorithm.DoesNotExist:
            raise CommandError(f"Algorithm {classifier_id} does not exist.")

    def _report(self, project: Project | None, result) -> None:
        scope = f"project {project.pk} {project.name!r}" if project else "global"
        suffix = " [dry-run]" if result.dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"[{scope}] region={result.region_code} saved={result.saved_list_size} "
                f"(covered={result.model_covered}, uncovered={result.regional_no_model_coverage}, "
                f"created={result.created_taxa}, in_db={result.already_in_db}, "
                f"regional_total={result.regional_total}){suffix}"
            )
        )
