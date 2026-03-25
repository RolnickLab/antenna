"""
Management command to move deployments (and all related data) from one project to another.

Usage:
    # Dry run (default) — shows what would happen
    python manage.py reassign_deployments --source-project 20 --target-project 99 --deployment-ids 60,61

    # Execute the move
    python manage.py reassign_deployments --source-project 20 --target-project 99 --deployment-ids 60,61 --execute

    # Create a new target project
    python manage.py reassign_deployments --source-project 20 \
        --create-project "Nunavik" --deployment-ids 60,61 --execute

See docs/claude/planning/deployment-reassignment-guide.md for the full relationship map.
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from ami.jobs.models import Job
from ami.main.models import (
    Classification,
    Deployment,
    Detection,
    Event,
    Identification,
    Occurrence,
    Project,
    SourceImage,
    SourceImageCollection,
    Taxon,
)
from ami.ml.models import ProjectPipelineConfig

logger = logging.getLogger(__name__)


def collect_deployment_snapshot(dep_id: int) -> dict:
    """Capture row counts for a single deployment."""
    return {
        "events": Event.objects.filter(deployment_id=dep_id).count(),
        "source_images": SourceImage.objects.filter(deployment_id=dep_id).count(),
        "occurrences": Occurrence.objects.filter(deployment_id=dep_id).count(),
        "detections": Detection.objects.filter(source_image__deployment_id=dep_id).count(),
        "classifications": Classification.objects.filter(detection__source_image__deployment_id=dep_id).count(),
        "identifications": Identification.objects.filter(occurrence__deployment_id=dep_id).count(),
        "jobs": Job.objects.filter(deployment_id=dep_id).count(),
    }


def collect_aggregate_snapshot(deployment_ids: list[int]) -> dict:
    """Capture aggregate row counts for all related models."""
    return {
        "deployments": Deployment.objects.filter(pk__in=deployment_ids).count(),
        "events": Event.objects.filter(deployment_id__in=deployment_ids).count(),
        "source_images": SourceImage.objects.filter(deployment_id__in=deployment_ids).count(),
        "occurrences": Occurrence.objects.filter(deployment_id__in=deployment_ids).count(),
        "detections": Detection.objects.filter(source_image__deployment_id__in=deployment_ids).count(),
        "classifications": Classification.objects.filter(
            detection__source_image__deployment_id__in=deployment_ids
        ).count(),
        "identifications": Identification.objects.filter(occurrence__deployment_id__in=deployment_ids).count(),
        "jobs": Job.objects.filter(deployment_id__in=deployment_ids).count(),
    }


def collect_project_counts(project_id: int) -> dict:
    """Capture high-level project counts."""
    return {
        "deployments": Deployment.objects.filter(project_id=project_id).count(),
        "events": Event.objects.filter(project_id=project_id).count(),
        "source_images": SourceImage.objects.filter(project_id=project_id).count(),
        "occurrences": Occurrence.objects.filter(project_id=project_id).count(),
        "jobs": Job.objects.filter(project_id=project_id).count(),
    }


def link_processing_services_raw(source_project_id: int, target_project_id: int) -> int:
    """Link ProcessingServices via raw SQL to avoid ORM column mismatch issues."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO ml_processingservice_projects (processingservice_id, project_id)
            SELECT processingservice_id, %s
            FROM ml_processingservice_projects
            WHERE project_id = %s
            AND processingservice_id NOT IN (
                SELECT processingservice_id FROM ml_processingservice_projects WHERE project_id = %s
            )
            """,
            [target_project_id, source_project_id, target_project_id],
        )
        return cursor.rowcount


class Command(BaseCommand):
    help = "Move deployments and all related data from one project to another."

    def add_arguments(self, parser):
        parser.add_argument("--source-project", type=int, required=True, help="Source project ID")
        parser.add_argument("--target-project", type=int, help="Target project ID (must already exist)")
        parser.add_argument(
            "--create-project",
            type=str,
            help="Create a new target project with this name (instead of --target-project)",
        )
        parser.add_argument("--deployment-ids", type=str, required=True, help="Comma-separated deployment IDs to move")
        parser.add_argument(
            "--no-clone-pipelines",
            action="store_true",
            default=False,
            help="Skip cloning pipeline configs to target project",
        )
        parser.add_argument(
            "--no-clone-collections",
            action="store_true",
            default=False,
            help="Skip cloning mixed SourceImageCollections (images will just be removed from source collections)",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            default=False,
            help="Actually execute the move (default is dry run)",
        )

    def log(self, msg, style=None):
        """Write to stdout and logger."""
        if style:
            self.stdout.write(style(msg))
        else:
            self.stdout.write(msg)
        logger.info(msg)

    def handle(self, *args, **options):
        source_project_id = options["source_project"]
        deployment_ids = [int(x.strip()) for x in options["deployment_ids"].split(",")]
        execute = options["execute"]
        clone_pipelines = not options["no_clone_pipelines"]
        clone_collections = not options["no_clone_collections"]

        mode = "EXECUTE" if execute else "DRY RUN"
        self.log(f"\n{'=' * 60}")
        self.log(f"  DEPLOYMENT REASSIGNMENT — {mode}")
        self.log(f"{'=' * 60}")

        # --- Validate inputs ---
        try:
            source_project = Project.objects.get(pk=source_project_id)
        except Project.DoesNotExist:
            raise CommandError(f"Source project {source_project_id} does not exist")

        self.log(f"\nSource project: {source_project.name} (id={source_project.pk})")

        deployments = Deployment.objects.filter(pk__in=deployment_ids)
        if deployments.count() != len(deployment_ids):
            found = set(deployments.values_list("pk", flat=True))
            missing = set(deployment_ids) - found
            raise CommandError(f"Deployments not found: {missing}")

        wrong_project = deployments.exclude(project_id=source_project_id)
        if wrong_project.exists():
            wrong = {d.pk: d.project_id for d in wrong_project}
            raise CommandError(f"Deployments not in source project {source_project_id}: {wrong}")

        # Target project resolution
        create_project_name = options.get("create_project")
        if create_project_name:
            self.log(f"Target project: NEW — '{create_project_name}'")
            target_project = None
        elif options.get("target_project"):
            try:
                target_project = Project.objects.get(pk=options["target_project"])
            except Project.DoesNotExist:
                raise CommandError(f"Target project {options['target_project']} does not exist")
            create_project_name = None
            self.log(f"Target project: {target_project.name} (id={target_project.pk})")
        else:
            raise CommandError("Must specify either --target-project or --create-project")

        self.log(f"Deployments to move: {deployment_ids}")

        # --- Per-deployment before snapshot ---
        self.log(f"\n{'─' * 60}")
        self.log("  BEFORE — Per-deployment breakdown")
        self.log(f"{'─' * 60}")

        per_dep_snapshots = {}
        for dep in deployments:
            snap = collect_deployment_snapshot(dep.pk)
            per_dep_snapshots[dep.pk] = snap
            self.log(f"\n  {dep.name} (id={dep.pk}):")
            self.log(f"    Project:         {dep.project.name} (id={dep.project_id})")
            dev_name = dep.device.name if dep.device else "None"
            site_name = dep.research_site.name if dep.research_site else "None"
            self.log(f"    Device:          {dev_name} (id={dep.device_id})")
            self.log(f"    Site:            {site_name} (id={dep.research_site_id})")
            self.log(f"    S3 Source:       id={dep.data_source_id}")
            for model_name, count in snap.items():
                self.log(f"    {model_name:20s} {count:>10,}")

        # Aggregate snapshot
        self.log(f"\n{'─' * 60}")
        self.log("  BEFORE — Aggregate totals")
        self.log(f"{'─' * 60}")

        pre_snapshot = collect_aggregate_snapshot(deployment_ids)
        for model_name, count in pre_snapshot.items():
            self.log(f"  {model_name:20s} {count:>10,}")

        source_pre = collect_project_counts(source_project_id)
        self.log(f"\n  Source project totals ({source_project.name}):")
        for model_name, count in source_pre.items():
            self.log(f"    {model_name:20s} {count:>10,}")

        if target_project:
            target_pre = collect_project_counts(target_project.pk)
            self.log(f"\n  Target project totals ({target_project.name}):")
            for model_name, count in target_pre.items():
                self.log(f"    {model_name:20s} {count:>10,}")

        # --- Shared resource analysis ---
        self.log(f"\n{'─' * 60}")
        self.log("  SHARED RESOURCE ANALYSIS")
        self.log(f"{'─' * 60}")

        # S3StorageSources
        s3_sources = {}
        for dep in deployments:
            if dep.data_source_id:
                s3_sources[dep.data_source_id] = dep.data_source
        for s3_id, s3 in s3_sources.items():
            other_deps = Deployment.objects.filter(data_source_id=s3_id).exclude(pk__in=deployment_ids)
            if other_deps.exists():
                others = ", ".join(f"{d.name}(id={d.pk})" for d in other_deps[:5])
                n = other_deps.count()
                self.log(f"  S3StorageSource {s3_id} (project={s3.project_id}):" f" SHARED with {n} others [{others}]")
            else:
                self.log(f"  S3StorageSource {s3_id} (project={s3.project_id}): exclusive to moved deployments")

        # Devices
        devices = {}
        for dep in deployments:
            if dep.device_id:
                devices[dep.device_id] = dep.device
        for dev_id, dev in devices.items():
            other_deps = Deployment.objects.filter(device_id=dev_id).exclude(pk__in=deployment_ids)
            action = (
                "no change needed (project=NULL)"
                if dev.project_id is None
                else (
                    f"will CLONE (owned by source project {dev.project_id})"
                    if dev.project_id == source_project_id and other_deps.exists()
                    else f"will REASSIGN (owned by source project {dev.project_id})"
                    if dev.project_id == source_project_id
                    else f"no change needed (owned by project {dev.project_id})"
                )
            )
            self.log(f"  Device '{dev.name}' (id={dev_id}): {action}")

        # Sites
        sites = {}
        for dep in deployments:
            if dep.research_site_id:
                sites[dep.research_site_id] = dep.research_site
        for site_id, site in sites.items():
            other_deps = Deployment.objects.filter(research_site_id=site_id).exclude(pk__in=deployment_ids)
            action = (
                "no change needed (project=NULL)"
                if site.project_id is None
                else (
                    f"will CLONE (owned by source project {site.project_id})"
                    if site.project_id == source_project_id and other_deps.exists()
                    else f"will REASSIGN (owned by source project {site.project_id})"
                    if site.project_id == source_project_id
                    else f"no change needed (owned by project {site.project_id})"
                )
            )
            self.log(f"  Site '{site.name}' (id={site_id}): {action}")

        # Collections
        mixed_collections = []
        exclusive_collections = []
        collections = SourceImageCollection.objects.filter(
            project_id=source_project_id,
            images__deployment_id__in=deployment_ids,
        ).distinct()
        for coll in collections:
            target_count = coll.images.filter(deployment_id__in=deployment_ids).count()
            other_count = coll.images.exclude(deployment_id__in=deployment_ids).count()
            if other_count > 0:
                mixed_collections.append((coll, target_count, other_count))
                action = f"MIXED — {target_count} moving, {other_count} staying"
                if clone_collections:
                    action += " → will SPLIT (clone to target, remove from source)"
                else:
                    action += " → will REMOVE moved images from source only"
            else:
                exclusive_collections.append(coll)
                action = f"EXCLUSIVE — all {target_count} images moving → will REASSIGN"
            self.log(f"  Collection '{coll.name}' (id={coll.pk}): {action}")

        # Taxa
        taxa_ids = set(
            Occurrence.objects.filter(deployment_id__in=deployment_ids)
            .exclude(determination__isnull=True)
            .values_list("determination_id", flat=True)
            .distinct()
        )
        self.log(f"\n  Taxa referenced by moved occurrences: {len(taxa_ids)}")

        if not execute:
            self.log(
                f"\n{'=' * 60}\n  DRY RUN COMPLETE — no changes made.\n"
                f"  Re-run with --execute to proceed.\n{'=' * 60}",
                style=self.style.WARNING,
            )
            return

        # === EXECUTE ===
        self.log(f"\n{'─' * 60}")
        self.log("  EXECUTING MOVE")
        self.log(f"{'─' * 60}")

        with transaction.atomic():
            # 0. Create target project inside transaction
            if create_project_name:
                target_project = Project(name=create_project_name, owner=source_project.owner)
                target_project.save()
                for membership in source_project.project_memberships.all():
                    target_project.members.add(membership.user)
                self.log(f"  [1/12] Created project '{target_project.name}' (id={target_project.pk})")
                target_pre = collect_project_counts(target_project.pk)
            else:
                self.log(f"  [1/12] Using existing project '{target_project.name}' (id={target_project.pk})")

            target_id = target_project.pk

            # 1. Clone or reassign S3StorageSources
            s3_clone_map = {}
            for s3_id, s3 in s3_sources.items():
                if s3.project_id == source_project_id:
                    other_deps = Deployment.objects.filter(data_source_id=s3_id).exclude(pk__in=deployment_ids)
                    if other_deps.exists():
                        old_pk = s3.pk
                        s3.pk = None
                        s3.project_id = target_id
                        s3.save()
                        s3_clone_map[old_pk] = s3.pk
                        self.log(f"  [2/12] Cloned S3StorageSource {old_pk} → {s3.pk}")
                    else:
                        s3.project_id = target_id
                        s3.save()
                        self.log(f"  [2/12] Reassigned S3StorageSource {s3_id}")

            # 2. Clone or reassign Devices
            device_clone_map = {}
            for dev_id, dev in devices.items():
                if dev.project_id == source_project_id:
                    other_deps = Deployment.objects.filter(device_id=dev_id).exclude(pk__in=deployment_ids)
                    if other_deps.exists():
                        old_pk = dev.pk
                        dev.pk = None
                        dev.project_id = target_id
                        dev.save()
                        device_clone_map[old_pk] = dev.pk
                        self.log(f"  [3/12] Cloned Device '{dev.name}' {old_pk} → {dev.pk}")
                    else:
                        dev.project_id = target_id
                        dev.save()
                        self.log(f"  [3/12] Reassigned Device '{dev.name}' {dev_id}")

            # 3. Clone or reassign Sites
            site_clone_map = {}
            for site_id, site in sites.items():
                if site.project_id == source_project_id:
                    other_deps = Deployment.objects.filter(research_site_id=site_id).exclude(pk__in=deployment_ids)
                    if other_deps.exists():
                        old_pk = site.pk
                        site.pk = None
                        site.project_id = target_id
                        site.save()
                        site_clone_map[old_pk] = site.pk
                        self.log(f"  [4/12] Cloned Site '{site.name}' {old_pk} → {site.pk}")
                    else:
                        site.project_id = target_id
                        site.save()
                        self.log(f"  [4/12] Reassigned Site '{site.name}' {site_id}")

            # 4. Update Deployments
            for dep in deployments:
                old_project = dep.project_id
                dep.project_id = target_id
                if dep.data_source_id in s3_clone_map:
                    dep.data_source_id = s3_clone_map[dep.data_source_id]
                if dep.device_id in device_clone_map:
                    dep.device_id = device_clone_map[dep.device_id]
                if dep.research_site_id in site_clone_map:
                    dep.research_site_id = site_clone_map[dep.research_site_id]
                dep.save(update_calculated_fields=False, regroup_async=False)
                self.log(
                    f"  [5/12] Moved Deployment '{dep.name}' (id={dep.pk}) " f"project {old_project} → {target_id}"
                )

            # 5. Bulk update Events
            event_count = Event.objects.filter(deployment_id__in=deployment_ids).update(project_id=target_id)
            self.log(f"  [6/12] Updated {event_count:,} Events")

            # 6. Bulk update SourceImages
            img_count = SourceImage.objects.filter(deployment_id__in=deployment_ids).update(project_id=target_id)
            self.log(f"  [7/12] Updated {img_count:,} SourceImages")

            # 7. Bulk update Occurrences
            occ_count = Occurrence.objects.filter(deployment_id__in=deployment_ids).update(project_id=target_id)
            self.log(f"  [8/12] Updated {occ_count:,} Occurrences")

            # 8. Bulk update Jobs
            job_count = Job.objects.filter(deployment_id__in=deployment_ids).update(project_id=target_id)
            self.log(f"  [9/12] Updated {job_count:,} Jobs")

            # 9. Handle collections
            for coll, target_count, other_count in mixed_collections:
                moved_images = coll.images.filter(deployment_id__in=deployment_ids)
                moved_image_ids = list(moved_images.values_list("pk", flat=True))

                if clone_collections:
                    new_coll = SourceImageCollection.objects.create(
                        name=coll.name,
                        project_id=target_id,
                        description=coll.description or "",
                    )
                    new_coll.images.set(moved_image_ids)
                    self.log(
                        f"  [10/12] Split collection '{coll.name}': "
                        f"cloned {len(moved_image_ids):,} images → target collection id={new_coll.pk}"
                    )

                coll.images.remove(*moved_image_ids)
                self.log(f"  [10/12] Removed {len(moved_image_ids):,} images from source collection '{coll.name}'")

            for coll in exclusive_collections:
                coll.project_id = target_id
                coll.save()
                self.log(f"  [10/12] Reassigned collection '{coll.name}' (id={coll.pk})")

            # 10. Clone pipeline configs
            if clone_pipelines:
                existing_pipelines = set(
                    ProjectPipelineConfig.objects.filter(project_id=target_id).values_list("pipeline_id", flat=True)
                )
                cloned_count = 0
                for config in ProjectPipelineConfig.objects.filter(project_id=source_project_id):
                    if config.pipeline_id not in existing_pipelines:
                        ProjectPipelineConfig.objects.create(project_id=target_id, pipeline_id=config.pipeline_id)
                        cloned_count += 1
                total = ProjectPipelineConfig.objects.filter(project_id=target_id).count()
                self.log(f"  [11/12] Pipeline configs: cloned {cloned_count}, target now has {total}")

            # 11. Link ProcessingServices (raw SQL to avoid ORM column mismatch)
            linked = link_processing_services_raw(source_project_id, target_id)
            self.log(f"  [11/12] Linked {linked} ProcessingService(s) to target project")

            # 12. Link taxa to target project
            if taxa_ids:
                for taxon in Taxon.objects.filter(pk__in=taxa_ids):
                    taxon.projects.add(target_project)
                self.log(f"  [12/12] Linked {len(taxa_ids):,} taxa to target project")
            else:
                self.log("  [12/12] No taxa to link (no occurrences with determinations)")

        # --- Post-move: update cached fields (outside transaction) ---
        self.log(f"\n{'─' * 60}")
        self.log("  UPDATING CACHED FIELDS")
        self.log(f"{'─' * 60}")

        # Update deployment cached counts
        for dep in Deployment.objects.filter(pk__in=deployment_ids):
            dep.update_calculated_fields(save=True)
            self.log(f"  Deployment '{dep.name}' (id={dep.pk}): cached fields updated")

        # Update event cached counts for moved events
        from ami.main.models import update_calculated_fields_for_events

        moved_event_pks = list(Event.objects.filter(deployment_id__in=deployment_ids).values_list("pk", flat=True))
        if moved_event_pks:
            update_calculated_fields_for_events(pks=moved_event_pks)
            self.log(f"  Updated cached fields for {len(moved_event_pks)} events")

        # Update both projects' related calculated fields (events + deployments)
        self.log(f"  Updating source project cached fields...")
        source_project.update_related_calculated_fields()
        self.log(f"  Source project '{source_project.name}': related fields updated")

        self.log(f"  Updating target project cached fields...")
        target_project.update_related_calculated_fields()
        self.log(f"  Target project (id={target_id}): related fields updated")

        # --- Post-move: per-deployment after snapshot ---
        self.log(f"\n{'─' * 60}")
        self.log("  AFTER — Per-deployment breakdown")
        self.log(f"{'─' * 60}")

        all_ok = True
        for dep in Deployment.objects.filter(pk__in=deployment_ids).select_related(
            "project", "device", "research_site"
        ):
            snap_after = collect_deployment_snapshot(dep.pk)
            snap_before = per_dep_snapshots[dep.pk]
            self.log(f"\n  {dep.name} (id={dep.pk}):")
            self.log(f"    Project:         {dep.project.name} (id={dep.project_id})")
            dev_name = dep.device.name if dep.device else "None"
            site_name = dep.research_site.name if dep.research_site else "None"
            self.log(f"    Device:          {dev_name} (id={dep.device_id})")
            self.log(f"    Site:            {site_name} (id={dep.research_site_id})")
            self.log(f"    S3 Source:       id={dep.data_source_id}")
            for model_name in snap_after:
                before = snap_before[model_name]
                after = snap_after[model_name]
                status = "OK" if before == after else "MISMATCH"
                if status != "OK":
                    all_ok = False
                self.log(f"    {model_name:20s} before={before:>10,}  after={after:>10,}  {status}")

        # --- Post-move: aggregate snapshot ---
        self.log(f"\n{'─' * 60}")
        self.log("  AFTER — Aggregate totals")
        self.log(f"{'─' * 60}")

        post_snapshot = collect_aggregate_snapshot(deployment_ids)
        for model_name, count in post_snapshot.items():
            pre_count = pre_snapshot[model_name]
            status = "OK" if count == pre_count else f"MISMATCH (was {pre_count})"
            if count != pre_count:
                all_ok = False
            self.log(f"  {model_name:20s} {count:>10,}  {status}")

        source_post = collect_project_counts(source_project_id)
        self.log(f"\n  Source project ({source_project.name}) after move:")
        for model_name, count in source_post.items():
            diff = source_pre[model_name] - count
            self.log(f"    {model_name:20s} {count:>10,}  (moved {diff:,})")

        target_post = collect_project_counts(target_id)
        self.log(f"\n  Target project (id={target_id}) after move:")
        for model_name, count in target_post.items():
            self.log(f"    {model_name:20s} {count:>10,}")

        # --- Validation ---
        self.log(f"\n{'─' * 60}")
        self.log("  VALIDATION")
        self.log(f"{'─' * 60}")
        errors = []

        # FK integrity: all moved data points to target project
        for model_name, model_cls, filter_field in [
            ("Events", Event, "deployment_id__in"),
            ("SourceImages", SourceImage, "deployment_id__in"),
            ("Occurrences", Occurrence, "deployment_id__in"),
            ("Jobs", Job, "deployment_id__in"),
        ]:
            bad = model_cls.objects.filter(**{filter_field: deployment_ids}).exclude(project_id=target_id).count()
            if bad:
                errors.append(f"{bad} {model_name} still pointing to wrong project")
                self.log(f"  FAIL: {bad} {model_name} still pointing to wrong project")
            else:
                self.log(f"  OK: All {model_name} point to target project")

        # Indirect access consistency
        dets_via_project = Detection.objects.filter(source_image__project_id=target_id).count()
        dets_via_dep = Detection.objects.filter(source_image__deployment_id__in=deployment_ids).count()
        if dets_via_project != dets_via_dep:
            errors.append(f"Detection count mismatch: via project={dets_via_project}, via deployment={dets_via_dep}")
            self.log(
                f"  FAIL: Detection count mismatch: via project={dets_via_project}, via deployment={dets_via_dep}"
            )
        else:
            self.log(
                f"  OK: Detections consistent ({dets_via_project:,} via project, {dets_via_dep:,} via deployment)"
            )

        cls_via_project = Classification.objects.filter(detection__source_image__project_id=target_id).count()
        cls_via_dep = Classification.objects.filter(detection__source_image__deployment_id__in=deployment_ids).count()
        if cls_via_project != cls_via_dep:
            errors.append(
                f"Classification count mismatch: via project={cls_via_project}, via deployment={cls_via_dep}"
            )
        else:
            self.log(f"  OK: Classifications consistent ({cls_via_project:,})")

        idents_via_project = Identification.objects.filter(occurrence__project_id=target_id).count()
        idents_via_dep = Identification.objects.filter(occurrence__deployment_id__in=deployment_ids).count()
        if idents_via_project != idents_via_dep:
            errors.append(
                f"Identification count mismatch: via project={idents_via_project}, via deployment={idents_via_dep}"
            )
        else:
            self.log(f"  OK: Identifications consistent ({idents_via_project:,})")

        # Source project has no leaked data from moved deployments
        for model_name, model_cls in [("Events", Event), ("SourceImages", SourceImage), ("Occurrences", Occurrence)]:
            leaked = model_cls.objects.filter(project_id=source_project_id, deployment_id__in=deployment_ids).count()
            if leaked:
                errors.append(f"{leaked} {model_name} leaked in source project")
            else:
                self.log(f"  OK: No {model_name} leaked in source project")

        # Collection integrity
        source_colls = SourceImageCollection.objects.filter(project_id=source_project_id)
        for coll in source_colls:
            leaked = coll.images.filter(deployment_id__in=deployment_ids).count()
            if leaked:
                errors.append(f"Source collection '{coll.name}' still has {leaked} moved images")
        self.log(f"  OK: No moved images in source collections" if not any("collection" in e for e in errors) else "")

        # Conservation: source + target = original totals
        for model_name in source_pre:
            combined = source_post[model_name] + target_post[model_name]
            original = source_pre[model_name] + target_pre.get(model_name, 0)
            if combined != original:
                errors.append(
                    f"Conservation failed for {model_name}: "
                    f"source({source_post[model_name]}) + target({target_post[model_name]}) = {combined} "
                    f"!= original({original})"
                )
            else:
                self.log(f"  OK: Conservation check passed for {model_name} ({combined:,} = {original:,})")

        # Per-deployment row count integrity
        if not all_ok:
            errors.append("Per-deployment row counts changed (see breakdown above)")

        # --- Final verdict ---
        self.log(f"\n{'=' * 60}")
        if errors:
            self.log("  VALIDATION FAILED", style=self.style.ERROR)
            for err in errors:
                self.log(f"    ✗ {err}", style=self.style.ERROR)
        else:
            self.log("  ALL VALIDATION CHECKS PASSED", style=self.style.SUCCESS)
        self.log(f"{'=' * 60}")
