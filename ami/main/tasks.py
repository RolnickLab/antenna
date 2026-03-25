import logging

from config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(soft_time_limit=300, time_limit=360)
def check_data_integrity():
    """
    Periodic task to find and fix occurrences missing determinations.

    Register via django_celery_beat in Django admin:
        Task: ami.main.tasks.check_data_integrity
        Schedule: e.g. every 24 hours
    """
    from ami.main.integrity import reconcile_missing_determinations

    result = reconcile_missing_determinations()
    logger.info(f"Data integrity check: {result.checked} checked, {result.fixed} fixed, {result.unfixable} unfixable")
    return {"checked": result.checked, "fixed": result.fixed, "unfixable": result.unfixable}
