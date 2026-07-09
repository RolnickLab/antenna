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
def generate_regional_taxa_list_task(
    *,
    project_id: int,
    region_source: str,
    region_code: str,
    site_id: int | None = None,
    classifier_id: int | None = None,
    include_uncovered: bool = False,
) -> None:
    """Build a regional taxa list for a project (or one of its sites) and link it.

    Runs off the request path because the external biodiversity-database fetch can
    take tens of seconds — too long for an admin request. Enqueued from the Project
    and Site admin actions. On success the generated list is attached to
    ``project.default_taxa_list`` (project scope) or ``site.taxa_list`` (site scope),
    which is what the masking auto-resolution later reads. See
    ``ami.main.services.regional_taxa`` and issue #1364.
    """
    from ami.main.models import Project, Site, TaxaList
    from ami.main.services import regional_taxa

    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        logger.warning(f"Project {project_id} not found; skipping regional taxa-list generation")
        return

    classifier = None
    if classifier_id:
        from ami.ml.models.algorithm import Algorithm

        classifier = Algorithm.objects.filter(pk=classifier_id).first()

    result = regional_taxa.generate_regional_taxa_list(
        project=project,
        region_source=region_source,
        region_code=region_code,
        classifier=classifier,
        include_uncovered=include_uncovered,
    )
    if result.taxa_list_id is None:
        return

    taxa_list = TaxaList.objects.get(pk=result.taxa_list_id)
    if site_id is not None:
        site = Site.objects.filter(pk=site_id).first()
        if site is not None:
            site.taxa_list = taxa_list
            site.save(update_fields=["taxa_list"])
    else:
        project.default_taxa_list = taxa_list
        project.save(update_fields=["default_taxa_list"])

    logger.info(
        "Regional taxa list %s (%s taxa) linked to %s",
        taxa_list.pk,
        result.saved_list_size,
        f"site {site_id}" if site_id else f"project {project_id}",
    )
