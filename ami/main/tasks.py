import logging

from ami.tasks import default_soft_time_limit, default_time_limit
from config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(soft_time_limit=default_soft_time_limit, time_limit=default_time_limit)
def check_data_integrity():
    """Periodic integrity check for occurrence data.

    Schedule via django_celery_beat in the Django admin:
        Task: ami.main.tasks.check_data_integrity
    """
    from ami.main.checks import reconcile_missing_determinations

    result = reconcile_missing_determinations(dry_run=False)
    logger.info(
        "Data integrity check: %d checked, %d fixed, %d unfixable",
        result.checked,
        result.fixed,
        result.unfixable,
    )
    return {
        "checked": result.checked,
        "fixed": result.fixed,
        "unfixable": result.unfixable,
    }
