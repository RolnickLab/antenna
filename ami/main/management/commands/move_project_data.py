"""
Move deployments and ALL associated data from one project to another.

This is a comprehensive data transfer: deployments, source images, events,
occurrences, detections, classifications, identifications, jobs, collection
memberships, taxa links, pipeline configs, and processing service links.

Usage:
    # Dry run (default) — shows what would happen
    python manage.py move_project_data --source-project 20 --target-project 99 --deployment-ids 60,61

    # Execute the move
    python manage.py move_project_data --source-project 20 --target-project 99 --deployment-ids 60,61 --execute

    # Create a new target project
    python manage.py move_project_data --source-project 20 \
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
    TaxaList,
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


def clone_or_reassign(obj, deployment_ids, source_project_id, target_project_id, fk_field, label, log):
    """Clone obj if shared with non-moved deployments, else reassign to target.

    Returns (action, old_pk, new_pk). action in ('cloned', 'reassigned', 'skipped').
    Skips silently when obj.project_id is NULL (global) or owned by another project.
    """
    if obj.project_id is None:
        log(f"  [{label}] {obj.pk}: skipped (project=NULL, global)")
        return ("skipped", obj.pk, obj.pk)
    if obj.project_id != source_project_id:
        log(f"  [{label}] {obj.pk}: skipped (owned by project {obj.project_id})")
        return ("skipped", obj.pk, obj.pk)
    other_deps = Deployment.objects.filter(**{fk_field: obj.pk}).exclude(pk__in=deployment_ids)
    if other_deps.exists():
        old_pk = obj.pk
        obj.pk = None
        obj.project_id = target_project_id
        obj.save()
        log(f"  [{label}] Cloned {old_pk} -> {obj.pk}")
        return ("cloned", old_pk, obj.pk)
    old_pk = obj.pk
    obj.project_id = target_project_id
    obj.save()
    log(f"  [{label}] Reassigned {obj.pk}")
    return ("reassigned", old_pk, obj.pk)


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
    help = "Move deployments and all associated data (images, occurrences, identifications, etc.) between projects."

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
        parser.add_argument(
            "--fire-post-save",
            action="store_true",
            default=False,
            help=(
                "After commit, call full Deployment.save() (regroup_async=True) on each moved deployment "
                "to fire post_save signals. Off by default — bulk .update() bypasses post_save and the script "
                "compensates only for cached counts. Enable when downstream listeners (search index, audit) "
                "must fire. Will also queue Celery event regrouping."
            ),
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
        deployment_ids = list(dict.fromkeys(int(x.strip()) for x in options["deployment_ids"].split(",")))
        execute = options["execute"]
        clone_pipelines = not options["no_clone_pipelines"]
        clone_collections = not options["no_clone_collections"]
        fire_post_save = options["fire_post_save"]

        mode = "EXECUTE" if execute else "DRY RUN"
        self.log(f"\n{'=' * 60}")
        self.log(f"  MOVE PROJECT DATA — {mode}")
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
        if create_project_name and options.get("target_project"):
            raise CommandError("Use either --target-project or --create-project, not both")
        if options.get("target_project") and options["target_project"] == source_project_id:
            raise CommandError("Target project cannot be the same as source project")

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

        target_pre = {}
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
                    else (
                        f"will REASSIGN (owned by source project {dev.project_id})"
                        if dev.project_id == source_project_id
                        else f"no change needed (owned by project {dev.project_id})"
                    )
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
                    else (
                        f"will REASSIGN (owned by source project {site.project_id})"
                        if site.project_id == source_project_id
                        else f"no change needed (owned by project {site.project_id})"
                    )
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

        # Identifiers: users who made identifications on moved data
        identifier_users = set(
            Identification.objects.filter(occurrence__deployment_id__in=deployment_ids)
            .exclude(user__isnull=True)
            .values_list("user_id", flat=True)
            .distinct()
        )
        # Map each identifier to the role they should get in the target project
        identifier_role_map = {}  # user_id -> role_class
        if identifier_users:
            from ami.users.models import User
            from ami.users.roles import Identifier, Role

            self.log("\n  Identifiers (users with identifications on moved data):")
            for uid in identifier_users:
                user = User.objects.get(pk=uid)
                source_role = Role.get_primary_role(source_project, user)
                if source_role:
                    role_to_assign = source_role
                    role_source = "source project role"
                else:
                    role_to_assign = Identifier
                    role_source = "default (not a source member)"
                identifier_role_map[uid] = role_to_assign
                self.log(f"    User id={uid}: " f"{role_to_assign.display_name} ({role_source})")

        # Default filter config
        self.log("\n  Source project default filters:")
        include_taxa = list(source_project.default_filters_include_taxa.values_list("name", flat=True))
        exclude_taxa = list(source_project.default_filters_exclude_taxa.values_list("name", flat=True))
        self.log(f"    Score threshold: {source_project.default_filters_score_threshold}")
        self.log(f"    Include taxa: {include_taxa or '(none)'}")
        self.log(f"    Exclude taxa: {exclude_taxa or '(none)'}")
        if include_taxa or exclude_taxa:
            self.log("    → Will copy default filter config to target project")

        # TaxaLists
        source_taxa_lists = TaxaList.objects.filter(projects=source_project)
        if source_taxa_lists.exists():
            self.log("\n  TaxaLists linked to source project:")
            for tl in source_taxa_lists:
                shared = tl.projects.count()
                self.log(
                    f"    '{tl.name}' (id={tl.pk}): {tl.taxa.count()} taxa,"
                    f" shared with {shared} project(s) → will link to target"
                )

        # --- Scope warning (conditional) ---
        has_processed_data = pre_snapshot["detections"] > 0
        has_identifications = pre_snapshot["identifications"] > 0
        has_classifications = pre_snapshot["classifications"] > 0

        self.log(f"\n{'─' * 60}")
        if has_processed_data:
            self.log("  SCOPE WARNING — This is a significant data transfer:")
            self.log(f"    {pre_snapshot['source_images']:>10,} source images")
            if has_processed_data:
                self.log(f"    {pre_snapshot['detections']:>10,} detections (ML predictions)")
            if has_classifications:
                self.log(f"    {pre_snapshot['classifications']:>10,} classifications")
            if has_identifications:
                self.log(f"    {pre_snapshot['identifications']:>10,} identifications (human reviews)")
            self.log(f"    {pre_snapshot['occurrences']:>10,} occurrences")
            self.log(f"    {pre_snapshot['jobs']:>10,} job records")
            self.log(f"    {len(taxa_ids):>10,} taxa references")
            if identifier_users:
                self.log(f"    {len(identifier_users):>10,} identifier user(s)")
            self.log("")
            self.log("  All of this data will be moved to the target project.")
            self.log("  The source project will no longer contain this data.")
        else:
            self.log("  This is a lightweight transfer (unprocessed image data).")
            self.log(f"    {pre_snapshot['source_images']:>10,} source images")
            self.log(f"    {pre_snapshot['events']:>10,} events")
        self.log(f"{'─' * 60}")

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
            # Create target project inside transaction
            if create_project_name:
                target_project = Project.objects.create(
                    name=create_project_name, owner=source_project.owner, create_defaults=True
                )
                for membership in source_project.project_memberships.all():
                    target_project.members.add(membership.user)
                self.log(f"  [create-target] Created project '{target_project.name}' (id={target_project.pk})")
                target_pre = collect_project_counts(target_project.pk)
            else:
                self.log(f"  [create-target] Using existing project '{target_project.name}' (id={target_project.pk})")

            target_id = target_project.pk

            # Clone or reassign shared resources
            s3_clone_map: dict[int, int] = {}
            for s3_id, s3 in s3_sources.items():
                action, old_pk, new_pk = clone_or_reassign(
                    s3, deployment_ids, source_project_id, target_id, "data_source_id", "clone-s3", self.log
                )
                if action == "cloned" and old_pk is not None and new_pk is not None:
                    s3_clone_map[old_pk] = new_pk

            device_clone_map: dict[int, int] = {}
            for dev_id, dev in devices.items():
                action, old_pk, new_pk = clone_or_reassign(
                    dev, deployment_ids, source_project_id, target_id, "device_id", "clone-device", self.log
                )
                if action == "cloned" and old_pk is not None and new_pk is not None:
                    device_clone_map[old_pk] = new_pk

            site_clone_map: dict[int, int] = {}
            for site_id, site in sites.items():
                action, old_pk, new_pk = clone_or_reassign(
                    site, deployment_ids, source_project_id, target_id, "research_site_id", "clone-site", self.log
                )
                if action == "cloned" and old_pk is not None and new_pk is not None:
                    site_clone_map[old_pk] = new_pk

            # Update Deployments
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
                self.log(f"  [move-deployment] '{dep.name}' (id={dep.pk}) project {old_project} -> {target_id}")

            # Bulk update related tables (.update() bypasses post_save — no listeners on these models today;
            # see _emit_post_save flag for opt-in trigger of Deployment post_save)
            event_count = Event.objects.filter(deployment_id__in=deployment_ids).update(project_id=target_id)
            self.log(f"  [move-events] Updated {event_count:,} Events")

            img_count = SourceImage.objects.filter(deployment_id__in=deployment_ids).update(project_id=target_id)
            self.log(f"  [move-images] Updated {img_count:,} SourceImages")

            occ_count = Occurrence.objects.filter(deployment_id__in=deployment_ids).update(project_id=target_id)
            self.log(f"  [move-occurrences] Updated {occ_count:,} Occurrences")

            job_count = Job.objects.filter(deployment_id__in=deployment_ids).update(project_id=target_id)
            self.log(f"  [move-jobs] Updated {job_count:,} Jobs")

            # Handle collections
            collection_clone_map: dict[int, int] = {}
            for coll, target_count, other_count in mixed_collections:
                moved_images = coll.images.filter(deployment_id__in=deployment_ids)
                moved_image_ids = list(moved_images.values_list("pk", flat=True))

                if clone_collections:
                    new_coll = SourceImageCollection.objects.create(
                        name=coll.name,
                        project_id=target_id,
                        description=coll.description or "",
                        method=coll.method,
                        kwargs=coll.kwargs or {},
                    )
                    new_coll.images.set(moved_image_ids)
                    collection_clone_map[coll.pk] = new_coll.pk
                    self.log(
                        f"  [handle-collections] Split '{coll.name}': "
                        f"cloned {len(moved_image_ids):,} images -> target collection id={new_coll.pk}"
                    )

                coll.images.remove(*moved_image_ids)
                self.log(
                    f"  [handle-collections] Removed {len(moved_image_ids):,} images "
                    f"from source collection '{coll.name}'"
                )

            for coll in exclusive_collections:
                coll.project_id = target_id
                coll.save()
                self.log(f"  [handle-collections] Reassigned collection '{coll.name}' (id={coll.pk})")

            # Remap moved Jobs whose source_image_collection points to a split source collection.
            # Exclusive collections were reassigned in place (same PK), so no remap needed.
            if collection_clone_map:
                remapped_total = 0
                for old_pk, new_pk in collection_clone_map.items():
                    n = Job.objects.filter(deployment_id__in=deployment_ids, source_image_collection_id=old_pk).update(
                        source_image_collection_id=new_pk
                    )
                    if n:
                        self.log(
                            f"  [remap-jobs-to-collections] {n} moved Job(s): "
                            f"source_image_collection {old_pk} -> {new_pk}"
                        )
                        remapped_total += n
                if not remapped_total:
                    self.log("  [remap-jobs-to-collections] No moved Jobs referenced split collections")
            elif mixed_collections and not clone_collections:
                # No-clone path: null out moved Jobs that reference mixed source collections.
                # Job loses its rerun target but no longer cross-links to source project.
                mixed_pks = [c.pk for c, _, _ in mixed_collections]
                nulled = Job.objects.filter(
                    deployment_id__in=deployment_ids, source_image_collection_id__in=mixed_pks
                ).update(source_image_collection_id=None)
                if nulled:
                    self.log(
                        f"  [remap-jobs-to-collections] WARN nulled source_image_collection on "
                        f"{nulled} moved Job(s) (mixed source collections were not cloned)"
                    )

            # DataExport residue: moved Jobs may still own a DataExport whose project_id is source.
            # DataExport is a historical artifact (S3-backed); leave it on source and surface count.
            export_residue = (
                Job.objects.filter(deployment_id__in=deployment_ids)
                .exclude(data_export__isnull=True)
                .exclude(data_export__project_id=target_id)
                .count()
            )
            if export_residue:
                self.log(
                    f"  [data-export-residue] {export_residue} moved Job(s) reference DataExport on "
                    f"another project (historical artifacts; not migrated)"
                )

            # Clone pipeline configs
            if clone_pipelines:
                existing_pipelines = set(
                    ProjectPipelineConfig.objects.filter(project_id=target_id).values_list("pipeline_id", flat=True)
                )
                cloned_count = 0
                for config in ProjectPipelineConfig.objects.filter(project_id=source_project_id):
                    if config.pipeline_id not in existing_pipelines:
                        ProjectPipelineConfig.objects.create(
                            project_id=target_id,
                            pipeline_id=config.pipeline_id,
                            enabled=config.enabled,
                            config=config.config,
                        )
                        cloned_count += 1
                total = ProjectPipelineConfig.objects.filter(project_id=target_id).count()
                self.log(f"  [clone-pipeline-config] Cloned {cloned_count}, target now has {total}")

            # Link ProcessingServices (raw SQL to avoid ORM column mismatch)
            linked = link_processing_services_raw(source_project_id, target_id)
            self.log(f"  [link-services] Linked {linked} ProcessingService(s) to target project")

            # Link taxa to target project
            if taxa_ids:
                target_project.taxa.add(*taxa_ids)
                self.log(f"  [link-taxa] Linked {len(taxa_ids):,} taxa to target project")
            else:
                self.log("  [link-taxa] No taxa to link (no occurrences with determinations)")

            # Add identifier users to target project, preserving roles
            if identifier_role_map:
                from ami.users.models import User

                target_member_ids = set(target_project.members.values_list("pk", flat=True))
                added_count = 0
                for uid, role_cls in identifier_role_map.items():
                    if uid not in target_member_ids:
                        user = User.objects.get(pk=uid)
                        target_project.members.add(user)
                        role_cls.assign_user(user, target_project)
                        added_count += 1
                        self.log(f"  [add-identifiers] Added user id={uid} as {role_cls.display_name}")
                if added_count == 0:
                    self.log("  [add-identifiers] All identifiers already members")
                else:
                    self.log(f"  [add-identifiers] Added {added_count} identifier(s)")
            else:
                self.log("  [add-identifiers] No identifier users to add")

            # Link TaxaLists to target project
            source_taxa_lists = TaxaList.objects.filter(projects=source_project)
            if source_taxa_lists.exists():
                for tl in source_taxa_lists:
                    tl.projects.add(target_project)
                self.log(f"  [link-taxalists] Linked {source_taxa_lists.count()} TaxaList(s) to target project")
            else:
                self.log("  [link-taxalists] No TaxaLists to link")

            # Copy default filter config to target project
            if include_taxa or exclude_taxa:
                for t in source_project.default_filters_include_taxa.all():
                    target_project.default_filters_include_taxa.add(t)
                for t in source_project.default_filters_exclude_taxa.all():
                    target_project.default_filters_exclude_taxa.add(t)
                self.log("  [copy-defaults] Copied default filter taxa config")
            target_project.default_filters_score_threshold = source_project.default_filters_score_threshold
            target_project.session_time_gap_seconds = source_project.session_time_gap_seconds
            if source_project.default_processing_pipeline:
                target_project.default_processing_pipeline = source_project.default_processing_pipeline
            target_project.save()
            self.log(f"  [copy-defaults] Score threshold: {target_project.default_filters_score_threshold}")
            self.log(f"  [copy-defaults] Session time gap (s): {target_project.session_time_gap_seconds}")

            # --- Validation (inside transaction — rolls back on failure) ---
            self.log(f"\n{'─' * 60}")
            self.log("  VALIDATION (inside transaction)")
            self.log(f"{'─' * 60}")
            errors = []

            # Per-deployment row count integrity
            all_ok = True
            for dep in Deployment.objects.filter(pk__in=deployment_ids).select_related(
                "project", "device", "research_site"
            ):
                snap_after = collect_deployment_snapshot(dep.pk)
                snap_before = per_dep_snapshots[dep.pk]
                for model_name in snap_after:
                    before = snap_before[model_name]
                    after = snap_after[model_name]
                    if before != after:
                        all_ok = False
                        self.log(f"  FAIL: {dep.name} {model_name}" f" before={before:,} after={after:,}")

            if not all_ok:
                errors.append("Per-deployment row counts changed (see above)")

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
            dets_via_project = Detection.objects.filter(
                source_image__project_id=target_id, source_image__deployment_id__in=deployment_ids
            ).count()
            dets_via_dep = Detection.objects.filter(source_image__deployment_id__in=deployment_ids).count()
            if dets_via_project != dets_via_dep:
                errors.append(
                    f"Detection count mismatch: via project={dets_via_project}, via deployment={dets_via_dep}"
                )
                self.log(
                    f"  FAIL: Detection count mismatch:"
                    f" via project={dets_via_project}, via deployment={dets_via_dep}"
                )
            else:
                self.log(
                    f"  OK: Detections consistent"
                    f" ({dets_via_project:,} via project, {dets_via_dep:,} via deployment)"
                )

            cls_via_project = Classification.objects.filter(
                detection__source_image__project_id=target_id,
                detection__source_image__deployment_id__in=deployment_ids,
            ).count()
            cls_via_dep = Classification.objects.filter(
                detection__source_image__deployment_id__in=deployment_ids
            ).count()
            if cls_via_project != cls_via_dep:
                errors.append(
                    f"Classification count mismatch:" f" via project={cls_via_project}, via deployment={cls_via_dep}"
                )
                self.log(
                    f"  FAIL: Classification count mismatch:"
                    f" via project={cls_via_project}, via deployment={cls_via_dep}"
                )
            else:
                self.log(f"  OK: Classifications consistent ({cls_via_project:,})")

            idents_via_project = Identification.objects.filter(
                occurrence__project_id=target_id, occurrence__deployment_id__in=deployment_ids
            ).count()
            idents_via_dep = Identification.objects.filter(occurrence__deployment_id__in=deployment_ids).count()
            if idents_via_project != idents_via_dep:
                errors.append(
                    f"Identification count mismatch:"
                    f" via project={idents_via_project}, via deployment={idents_via_dep}"
                )
                self.log(
                    f"  FAIL: Identification count mismatch:"
                    f" via project={idents_via_project}, via deployment={idents_via_dep}"
                )
            else:
                self.log(f"  OK: Identifications consistent ({idents_via_project:,})")

            # Source project has no leaked data from moved deployments
            for model_name, model_cls in [
                ("Events", Event),
                ("SourceImages", SourceImage),
                ("Occurrences", Occurrence),
            ]:
                leaked = model_cls.objects.filter(
                    project_id=source_project_id, deployment_id__in=deployment_ids
                ).count()
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
            if not any("collection" in e for e in errors):
                self.log("  OK: No moved images in source collections")

            # Job cross-link integrity: moved Jobs must not reference a SourceImageCollection on another project
            cross_linked_jobs = (
                Job.objects.filter(deployment_id__in=deployment_ids)
                .exclude(source_image_collection__isnull=True)
                .exclude(source_image_collection__project_id=target_id)
                .count()
            )
            if cross_linked_jobs:
                errors.append(
                    f"{cross_linked_jobs} moved Job(s) reference a source_image_collection on another project"
                )
                self.log(f"  FAIL: {cross_linked_jobs} moved Jobs cross-link to non-target collection")
            else:
                self.log("  OK: No moved Jobs cross-link to non-target collections")

            # Conservation: source + target = original totals
            source_post = collect_project_counts(source_project_id)
            target_post = collect_project_counts(target_id)
            for model_name in source_pre:
                combined = source_post[model_name] + target_post[model_name]
                original = source_pre[model_name] + target_pre.get(model_name, 0)
                if combined != original:
                    errors.append(
                        f"Conservation failed for {model_name}: "
                        f"source({source_post[model_name]})"
                        f" + target({target_post[model_name]})"
                        f" = {combined} != original({original})"
                    )
                else:
                    self.log(f"  OK: Conservation check passed for {model_name}" f" ({combined:,} = {original:,})")

            # --- Validation verdict (inside transaction) ---
            if errors:
                self.log(f"\n{'=' * 60}")
                self.log("  VALIDATION FAILED — ROLLING BACK", style=self.style.ERROR)
                for err in errors:
                    self.log(f"    ✗ {err}", style=self.style.ERROR)
                self.log(f"{'=' * 60}")
                raise CommandError(
                    "Post-move validation failed; transaction rolled back." " See log output above for details."
                )

            self.log("  ALL VALIDATION CHECKS PASSED")

        # --- Post-transaction: update cached fields (idempotent) ---
        self.log(f"\n{'─' * 60}")
        self.log("  UPDATING CACHED FIELDS")
        self.log(f"{'─' * 60}")

        for dep in Deployment.objects.filter(pk__in=deployment_ids):
            if fire_post_save:
                # Full save fires post_save and queues regroup_async (Celery event regrouping)
                dep.save()
                self.log(f"  Deployment '{dep.name}' (id={dep.pk}): full save (post_save fired, regroup queued)")
            else:
                dep.update_calculated_fields(save=True)
                self.log(f"  Deployment '{dep.name}' (id={dep.pk}): cached fields updated")

        from ami.main.models import update_calculated_fields_for_events

        moved_event_pks = list(Event.objects.filter(deployment_id__in=deployment_ids).values_list("pk", flat=True))
        if moved_event_pks:
            update_calculated_fields_for_events(pks=moved_event_pks)
            self.log(f"  Updated cached fields for {len(moved_event_pks)} events")

        self.log("  Updating source project cached fields...")
        source_project.update_related_calculated_fields()
        self.log(f"  Source project '{source_project.name}': related fields updated")

        self.log("  Updating target project cached fields...")
        target_project.update_related_calculated_fields()
        self.log(f"  Target project (id={target_id}): related fields updated")

        # --- Summary ---
        self.log(f"\n{'─' * 60}")
        self.log("  POST-MOVE SUMMARY")
        self.log(f"{'─' * 60}")

        source_final = collect_project_counts(source_project_id)
        self.log(f"\n  Source project ({source_project.name}):")
        for model_name, count in source_final.items():
            diff = source_pre[model_name] - count
            self.log(f"    {model_name:20s} {count:>10,}  (moved {diff:,})")

        target_final = collect_project_counts(target_id)
        self.log(f"\n  Target project (id={target_id}):")
        for model_name, count in target_final.items():
            self.log(f"    {model_name:20s} {count:>10,}")

        # Operator notes — surface non-obvious post-move state
        self.log(f"\n{'─' * 60}")
        self.log("  OPERATOR NOTES")
        self.log(f"{'─' * 60}")
        self.log(
            "  - Cache: django-cachalot and any UI cache may show stale counts briefly after commit. "
            "Refresh / wait for TTL to verify."
        )
        if not fire_post_save:
            self.log(
                "  - Signals: bulk .update() did not fire post_save on Event/SourceImage/Occurrence/Job. "
                "No listeners exist on these models today; pass --fire-post-save next time if downstream "
                "listeners are added (search index, audit log)."
            )
        else:
            self.log("  - Signals: post_save fired on each moved Deployment (regroup_async queued).")
        export_residue_final = (
            Job.objects.filter(project_id=target_id)
            .filter(deployment_id__in=deployment_ids)
            .exclude(data_export__isnull=True)
            .exclude(data_export__project_id=target_id)
            .count()
        )
        if export_residue_final:
            self.log(
                f"  - DataExport residue: {export_residue_final} moved Job(s) reference a DataExport on "
                f"another project. These are historical export artifacts and were intentionally left in place."
            )
        else:
            self.log("  - DataExport: no residue (no moved Jobs reference exports on other projects).")
        self.log(
            "  - Source project still owns: cloned shared resources (S3/Device/Site originals), TaxaLists "
            "(M2M; multi-project by design), and any taxa/filter taxa M2M entries — these were copied "
            "to target, not moved."
        )

        self.log(f"\n{'=' * 60}")
        self.log("  MOVE COMPLETE", style=self.style.SUCCESS)
        self.log(f"{'=' * 60}")
