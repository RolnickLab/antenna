import logging

from celery.signals import worker_ready
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from ami.ml.models.pipeline import Pipeline
from config.celery_app import app as celery_app

logger = logging.getLogger(__name__)

ANTENNA_CELERY_WORKER_NAME = "antenna_celeryworker"


def get_worker_name():
    """
    Find the antenna celery worker's node name.
    This is not always possible, especially if called too early during startup.
    """
    try:
        inspector = celery_app.control.inspect()
        active_workers = inspector.active()
        if active_workers:  # TODO: currently only works if there is one worker
            # NOTE: all antenna celery workers should have ANTENNA_CELERY_WORKER_NAME
            # in their name instead of the the default "celery"
            return next((worker for worker in active_workers.keys() if ANTENNA_CELERY_WORKER_NAME in worker), None)
    except Exception as e:
        logger.warning(f"Could not find antenna celery worker name: {e}")


@worker_ready.connect
def subscribe_celeryworker_to_pipeline_queues(sender, **kwargs) -> bool:
    """
    When the antenna worker is fully up, enqueue the subscription task.

    Returns True if subscriptions were successful, False otherwise.
    """
    if type(sender) == str:
        worker_name = sender
    elif sender is None:
        worker_name = get_worker_name()
    else:
        worker_name = sender.hostname  # e.g. "ANTENNA_CELERY_WORKER_NAME@<hostname>"
    assert worker_name, "Could not determine worker name; cannot subscribe to pipeline queues."
    pipelines = Pipeline.objects.values_list("slug", flat=True)

    if not worker_name.startswith(f"{ANTENNA_CELERY_WORKER_NAME}@"):
        logger.warning(
            f"Worker name '{worker_name}' does not match expected pattern "
            f"'{ANTENNA_CELERY_WORKER_NAME}@<hostname>'. Cannot subscribe to pipeline queues.",
        )
        return False

    if not pipelines:
        # TODO: kinda hacky. is there a way to unify the django and celery logs
        # to more easily see which queues the worker is subscribed to?
        raise ValueError("No pipelines found; cannot subscribe to any queues.")

    for slug in pipelines:
        queue_name = f"ml-pipeline-{slug}"
        try:
            celery_app.control.add_consumer(queue_name, destination=[worker_name])
            logger.info(f"Subscribed worker '{worker_name}' to queue '{queue_name}'")
        except Exception as e:
            logger.exception(f"Failed to subscribe '{worker_name}' to queue '{queue_name}': {e}")

    return True


@receiver(post_save, sender=Pipeline)
def pipeline_created(sender, instance, created, **kwargs):
    if not created:
        return

    try:
        queue_name = f"ml-pipeline-{instance.slug}"
        worker_name = get_worker_name()

        assert worker_name, (
            "Could not determine worker name; cannot subscribe to new queue "
            f"{queue_name}. This might be an expected error if the worker hasn't "
            "started or is ready to accept connections."
        )

        celery_app.control.add_consumer(queue_name, destination=[worker_name])
        logger.info(f"Queue '{queue_name}' successfully added to worker '{worker_name}'")
    except Exception as e:
        logger.exception(f"Failed to add queue '{queue_name}' to worker '{worker_name}': {e}.")


@receiver(post_delete, sender=Pipeline)
def pipeline_deleted(sender, instance, **kwargs):
    queue_name = f"ml-pipeline-{instance.slug}"
    logger.info(f"Unsubscribing queue '{queue_name}' from the celeryworker...")
    worker_name = get_worker_name()

    try:
        if not worker_name:
            raise ValueError("Could not determine worker name; cannot unsubscribe from queue.")

        celery_app.control.cancel_consumer(queue_name, destination=[worker_name])
        logger.info(f"Queue '{queue_name}' successfully unsubscribed from worker '{worker_name}'")
    except Exception as e:
        logger.exception(f"Failed to unsubscribe queue '{queue_name}' for worker '{worker_name}': {e}")
