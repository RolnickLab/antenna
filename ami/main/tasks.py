import logging

from django.apps import apps

from config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(ignore_result=True)
def recompute_cached_counts_task(model_label: str, pk: int) -> None:
    """Recompute one row's cached count columns.

    Dispatched by ``ami.base.cached_counts._flush_pending_recomputes`` after
    a transaction commits. Generic across every model that declares
    ``CachedCountField`` columns and implements ``update_calculated_fields``.

    Silent on missing rows: the row may have been deleted between when the
    recompute was queued and when the task runs.
    """
    model = apps.get_model(model_label)
    try:
        instance = model.objects.get(pk=pk)
    except model.DoesNotExist:
        logger.debug("recompute_cached_counts_task: %s pk=%s not found, skipping", model_label, pk)
        return
    instance.update_calculated_fields(save=True)


@celery_app.task(ignore_result=True)
def refresh_project_cached_counts(project_id: int) -> None:
    """Refresh cached counts on every Event, Deployment, and SourceImage in a project.

    Dispatched from signals on ``Project.default_filters_*`` changes. The
    cascade can touch tens of thousands of rows for a large project, so we
    do the work inline in this single Celery task rather than queueing one
    recompute task per row — that would flood the broker on a single filter
    change. ``Project.update_related_calculated_fields()`` keeps the bulk
    subquery UPDATE for ``SourceImage.detections_count`` while looping Events
    and Deployments row-by-row.
    """
    from ami.main.models import Project

    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        logger.warning(f"Project {project_id} not found; skipping cached-count refresh")
        return

    logger.info(f"Refreshing cached counts for project {project.pk} ({project.name})")
    project.update_related_calculated_fields()
