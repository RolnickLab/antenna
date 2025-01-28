import logging

from django.apps import apps
from django.db import models

from config import celery_app

logger = logging.getLogger(__name__)

one_hour = 60 * 60
one_day = one_hour * 24
two_days = one_hour * 24 * 2
default_time_limit = two_days + one_hour
default_soft_time_limit = two_days


# @TODO use shared_task decorator instead of celery_app?
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
def model_task(model_name: str, instance_id: int, method_name: str) -> None:
    Model = apps.get_model("main", model_name)
    instance = Model.objects.get(id=instance_id)
    method = getattr(instance, method_name)
    logger.info(f"Running '{method_name}' on {model_name} instance: '{instance}'")
    method()


@celery_app.task(soft_time_limit=one_hour, time_limit=one_hour + 60)
def model_bulk_update(Model: models.Model, instances: list, fields: list) -> None:
    logger.info(f"Bulk saving {len(instances)} {Model} instances (fields: {fields}))")
    Model.objects.bulk_update(instances, fields)


# Task to write tasks to Label Studio
@celery_app.task(soft_time_limit=one_hour, time_limit=one_hour + 60)
def write_tasks(label_studio_config_id: int) -> int:
    from ami.labelstudio.models import LabelStudioConfig

    config = LabelStudioConfig.objects.get(id=label_studio_config_id)
    if config:
        logger.info(f"Writing tasks for {config}")
        uploaded = config.write_tasks()
        return uploaded
    else:
        logger.error(f"LabelStudioConfig with id {label_studio_config_id} not found")
        return 0


# Task to populate SourceImageCollection with images
@celery_app.task(soft_time_limit=one_hour, time_limit=one_hour + 60)
def populate_collection(collection_id: int) -> None:
    from ami.main.models import SourceImageCollection

    collection = SourceImageCollection.objects.get(id=collection_id)
    if collection:
        logger.info(f"Populating collection {collection}")
        collection.populate_sample()
    else:
        logger.error(f"SourceImageCollection with id {collection_id} not found")


# Task to group images into events
@celery_app.task(soft_time_limit=one_hour, time_limit=one_hour + 60)
def regroup_events(deployment_id: int) -> None:
    from ami.main.models import Deployment, group_images_into_events

    deployment = Deployment.objects.get(id=deployment_id)
    if deployment:
        logger.info(f"Grouping captures for {deployment}")
        events = group_images_into_events(deployment)
        logger.info(f"{deployment } now has {len(events)} events")
    else:
        logger.error(f"Deployment with id {deployment_id} not found")


@celery_app.task(soft_time_limit=one_hour, time_limit=one_hour + 60)
def save_model_instance(app_label: str, model_name: str, pk: int | str) -> bool:
    """
    Call the save method on a model instance.
    """
    Model = apps.get_model(app_label, model_name)
    instance = Model.objects.get(pk=pk)
    instance.save()
    return True


@celery_app.task(soft_time_limit=one_hour, time_limit=one_hour + 60)
def save_model_instances(app_label: str, model_name: str, pks: list[int | str], batch_size: int = 100):
    """
    Call the save method on many model instances.
    """
    Model = apps.get_model(app_label, model_name)
    instance_pks = Model.objects.filter(pk__in=pks).values_list("pk", flat=True)
    arguments = [(app_label, model_name, pk) for pk in instance_pks]
    logger.info(f"Saving {len(instance_pks)} instances of {app_label}.{model_name}")
    group = save_model_instance.chunks(arguments, batch_size).group()
    # Offset the start time to limit the number of tasks that are started at once
    results = group.skew(start=0.1, stop=0.1, step=0.1)()
    result = all(results)
    if not result:
        logger.error(f"Failed to save all {len(instance_pks)} instances of {app_label}.{model_name}")


@celery_app.task(soft_time_limit=10, time_limit=20)
def check_processing_services_online():
    """
    Check the status of all processing services and update last checked.
    """
    from ami.ml.models import ProcessingService

    logger.info("Checking if processing services are online.")

    services = ProcessingService.objects.all()

    for service in services:
        logger.info(f"Checking service {service}")
        try:
            status_response = service.get_status()
            logger.info(status_response)
        except Exception as e:
            logger.error(f"Error checking service {service}: {e}")
            continue
