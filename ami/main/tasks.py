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
