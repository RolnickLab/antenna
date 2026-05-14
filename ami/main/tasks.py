import logging

from config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(ignore_result=True)
def refresh_project_cached_counts(project_id: int) -> None:
    """Refresh cached counts for all Events and Deployments in a project.

    Dispatched from signals on ``Project.default_filters_*`` changes. The work
    fans out to every Event and Deployment in the project, so it must not run
    inline in the request/save path.
    """
    from ami.main.models import Project

    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        logger.warning(f"Project {project_id} not found; skipping cached-count refresh")
        return

    logger.info(f"Refreshing cached counts for project {project.pk} ({project.name})")
    project.update_related_calculated_fields()


@celery_app.task(ignore_result=True)
def refresh_collection_cached_counts(collection_id: int) -> None:
    """Recompute the 3 denormalized image counts on one SourceImageCollection.

    Dispatched on_commit by the Detection and m2m signal handlers so that
    high-volume write paths (ML pipeline, sample population) don't pay the
    aggregate cost inline.
    """
    from ami.main.models import SourceImageCollection

    try:
        collection = SourceImageCollection.objects.get(pk=collection_id)
    except SourceImageCollection.DoesNotExist:
        logger.warning(f"SourceImageCollection {collection_id} not found; skipping cached-count refresh")
        return
    collection.update_calculated_fields(save=True)


@celery_app.task(ignore_result=True)
def reconcile_cached_counts_task(project_id: int | None = None, dry_run: bool = False) -> dict:
    """Periodic drift check for every model with ``CachedCountField`` columns.

    Catches drift introduced by bulk write paths that skip signals
    (``bulk_create``, ``bulk_update``, raw SQL, ML post-processors). Default
    is repair mode; pass ``dry_run=True`` for report-only.
    """
    from ami.main.checks.cached_counts import reconcile_cached_counts

    result = reconcile_cached_counts(project_id=project_id, dry_run=dry_run)
    logger.info(
        "reconcile_cached_counts: checked=%d fixed=%d unfixable=%d (project_id=%s, dry_run=%s)",
        result.checked,
        result.fixed,
        result.unfixable,
        project_id,
        dry_run,
    )
    return {"checked": result.checked, "fixed": result.fixed, "unfixable": result.unfixable}
