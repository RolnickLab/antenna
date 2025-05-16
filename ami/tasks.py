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


@celery_app.task(soft_time_limit=one_hour, time_limit=one_hour + 60)
def merge_taxa(target_taxon_id: int, source_taxon_id: int):
    """
    Merge all data related to one taxon into another and deactivate the source taxon.

    Args:
        target_taxon_id: ID of the taxon that will remain active and receive all data
        source_taxon_id: ID of the taxon that will be marked inactive and have its data merged into the target

    Operations performed:
    - Reassign occurrences from source_taxon to target_taxon
    - Set source_taxon as synonym_of target_taxon
    - Move all direct children of source_taxon to target_taxon
    - Set source_taxon.active = False
    - Add source_taxon.projects to target_taxon.projects
    - Update all identifications to point to target_taxon
    """

    from django.db import transaction

    from ami.main.models import Taxon

    with transaction.atomic():
        target_taxon: Taxon = Taxon.objects.get(id=target_taxon_id)
        source_taxon: Taxon = Taxon.objects.get(id=source_taxon_id)

        # Update parent of all direct children
        children_to_update = source_taxon.direct_children.all()
        children_to_update.update(parent=target_taxon)

        # Update parent relationships for each child individually
        for child in target_taxon.direct_children.all():
            child.update_parents()

        source_taxon.active = False
        source_taxon.synonym_of = target_taxon  # type: ignore[assignment]
        source_taxon.save()

        if target_taxon.synonym_of == source_taxon:
            target_taxon.synonym_of = None

        # Merge basic attributes
        model_fields = Taxon._meta.get_fields()
        fields_to_fill = [
            "common_name_en",
            "gbif_taxon_key",
            "bold_taxon_bin",
            "inat_taxon_id",
            "fieldguide_id",
            # "lepsai_id",
            "cover_image_url",
            "cover_image_credit",
            "notes",
            "author",
            "authorship_date",
            "ordering",
            "sort_phylogeny",
        ]
        for field in model_fields:
            if field.name in fields_to_fill:
                if getattr(target_taxon, field.name) is None:
                    setattr(target_taxon, field.name, getattr(source_taxon, field.name))

        # Merge search names ArrayField
        if target_taxon.search_names and source_taxon.search_names:
            target_taxon.search_names = list(set(target_taxon.search_names + source_taxon.search_names))
        elif source_taxon.search_names:
            target_taxon.search_names = source_taxon.search_names

        # Add scientific and common names from source_taxon to target_taxon's search_names (if they don't match)
        assert target_taxon.search_names is not None
        name_fields = ["name", "common_name_en"]
        for field in name_fields:
            source_value = getattr(source_taxon, field)
            target_value = getattr(target_taxon, field)
            if source_value != target_value and source_value not in target_taxon.search_names:
                target_taxon.search_names.append(source_value)
        # Remove any None values from search_names
        target_taxon.search_names = [name for name in target_taxon.search_names if name is not None]

        target_taxon.save()

        for project in source_taxon.projects.all():
            target_taxon.projects.add(project)

        for taxa_list in source_taxon.lists.all():
            taxa_list.taxa.add(target_taxon)

        # Updating the classifications
        source_taxon.classifications.update(taxon=target_taxon)

        # Update identifications that point to the source taxon
        # @TODO consider adding a new identification for the target taxon instead of swapping the taxon
        source_taxon.identifications.update(taxon=target_taxon)

        # Update occurrences' determinations through the model's update method
        # This avoids direct assignment to the determination field which appears to be protected
        source_taxon.occurrences.update(determination=target_taxon)
