import logging

from django.apps import apps

from config import celery_app

logger = logging.getLogger(__name__)

one_hour = 60 * 60
one_day = one_hour * 24
two_days = one_hour * 24 * 2


@celery_app.task(soft_time_limit=two_days, time_limit=two_days + one_hour)
def sync_source_images(deployment_id: int) -> int:
    from ami.main.models import Deployment

    deployment = Deployment.objects.get(id=deployment_id)
    logger.info(f"Importing source images for {deployment}")
    return deployment.sync_captures()


@celery_app.task(soft_time_limit=two_days, time_limit=two_days + one_hour)
def calculate_storage_size(storage_source_id: int) -> int:
    from ami.main.models import S3StorageSource

    storage = S3StorageSource.objects.get(id=storage_source_id)
    logger.info(f"Calculating total storage size for {storage}")
    return storage.calculate_size()


@celery_app.task(soft_time_limit=one_hour, time_limit=one_hour + 60)
def update_public_urls(deployment_id: int, base_url: str) -> None:
    from ami.main.models import Deployment

    deployment = Deployment.objects.get(id=deployment_id)
    logger.info(f"Updating public_base_url for all captures from {deployment}")
    deployment.captures.update(public_base_url=base_url)


@celery_app.task(soft_time_limit=one_hour, time_limit=one_hour + 60)
def model_task(model_name: str, model_id: int, method_name: str) -> None:
    Model = apps.get_model("main", model_name)
    instance = Model.objects.get(id=model_id)
    method = getattr(instance, method_name)
    logger.info(f"Running '{method_name}' on {model_name} instance: '{instance}'")
    method()
