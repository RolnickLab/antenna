import logging

from config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task()
def check_occurrences_task():
    """Periodic occurrence integrity check. Report-only, logs warnings."""
    from ami.main.checks import check_occurrences

    report = check_occurrences(fix=False)
    if report.has_issues:
        logger.warning("Occurrence integrity issues: %s", report.summary)
    else:
        logger.info("Occurrence integrity check passed")
    return report.summary
