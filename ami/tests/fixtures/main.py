import datetime
import logging
import os
import pathlib
import random
import uuid

from django.db import transaction
from django.utils import timezone

from ami.main.models import (
    Deployment,
    Detection,
    Occurrence,
    Project,
    SourceImage,
    SourceImageCollection,
    TaxaList,
    Taxon,
    TaxonRank,
    group_images_into_events,
)
from ami.ml.models.algorithm import Algorithm
from ami.ml.models.processing_service import ProcessingService
from ami.ml.tasks import create_detection_images
from ami.tests.fixtures.storage import GeneratedTestFrame, create_storage_source, populate_bucket
from ami.users.models import User

logger = logging.getLogger(__name__)


def update_site_settings(**kwargs):
    from django.contrib.sites.models import Site

    site = Site.objects.get_current()
    for key, value in kwargs.items():
        setattr(site, key, value)
    site.save()
    return site


def create_processing_service(project: Project, name: str = "Test Processing Service") -> ProcessingService:
    processing_service_to_add = {
        "name": name,
        "projects": [{"name": project.name}],
        # "endpoint_url": "http://processing_service:2000",
        "endpoint_url": "http://ml_backend:2000",
    }

    processing_service, created = ProcessingService.objects.get_or_create(
        name=processing_service_to_add["name"],
        endpoint_url=processing_service_to_add["endpoint_url"],
    )
    processing_service.save()

    if created:
        logger.info(f'Successfully created processing service with {processing_service_to_add["endpoint_url"]}.')
    else:
        logger.info(f'Using existing processing service with {processing_service_to_add["endpoint_url"]}.')

    for project_data in processing_service_to_add["projects"]:
        try:
            project = Project.objects.get(name=project_data["name"])
            processing_service.projects.add(project)
            processing_service.save()
        except Exception:
            logger.error(f'Could not find project {project_data["name"]}.')
    processing_service.get_status()
    processing_service.create_pipelines()

    return processing_service


def create_deployment(
    project: Project,
    data_source,
    name="Test Deployment",
) -> Deployment:
    """
    Create a test deployment with a data source for source images.
    """
    deployment, _ = Deployment.objects.get_or_create(
        project=project,
        name=name,
        defaults=dict(
            description=f"Created at {timezone.now()}",
            data_source=data_source,
            data_source_subdir="/",
            data_source_regex=".*\\.jpg",
            latitude=45.0,
            longitude=-123.0,
            research_site=project.sites.first(),
            device=project.devices.first(),
        ),
    )
    return deployment


def create_test_project(name: str | None) -> tuple[Project, str]:
    short_id = uuid.uuid4().hex[:8]
    name = name or f"Test Project {short_id}"

    with transaction.atomic():
        admin_user, _ = User.objects.get_or_create(
            email=f"antenna+{short_id}@insectai.org", is_superuser=True, is_staff=True
        )
        project = Project.objects.create(name=name, owner=admin_user, description="Test description")
        data_source = create_storage_source(project, f"Test Data Source {short_id}", prefix=f"{short_id}")
        create_deployment(project, data_source, f"Test Deployment {short_id}")
        create_processing_service(project, f"Test Processing Service {short_id}")
        return project, short_id


def setup_test_project(reuse=True) -> tuple[Project, Deployment]:
    """
    Always return a valid project and deployment, creating them if necessary.
    """
    project = None
    short_id = ""
    shared_test_project_name = "Shared Test Project"

    if reuse:
        project = Project.objects.filter(name=shared_test_project_name).first()
        if not project:
            project, short_id = create_test_project(name=shared_test_project_name)
    else:
        project, short_id = create_test_project(name=None)

    deployment = Deployment.objects.filter(project=project).filter(name__contains=short_id).latest("created_at")
    assert deployment, f"No deployment found for project {project}. Recreate the project."
    return project, deployment


def create_captures(
    deployment: Deployment,
    num_nights: int = 3,
    images_per_night: int = 3,
    interval_minutes: int = 10,
    subdir: str = "test",
    update_deployment: bool = True,
):
    # Create some images over a few monitoring nights
    first_night = datetime.datetime.now()

    created = []
    for night in range(num_nights):
        night_timestamp = first_night + datetime.timedelta(days=night)
        for i in range(images_per_night):
            random_prefix = uuid.uuid4().hex[:8]
            path = pathlib.Path(subdir) / f"{random_prefix}_{night}_{i}.jpg"
            img = SourceImage.objects.create(
                deployment=deployment,
                timestamp=night_timestamp + datetime.timedelta(minutes=i * interval_minutes),
                path=path,
            )
            created.append(img)

    collection = SourceImageCollection.objects.create(
        project=deployment.project,
        name="Test Source Image Collection",
    )
    collection.images.set(created)

    if update_deployment:
        # This should only be set to False when manually testing grouping images into events
        deployment.save(update_calculated_fields=True, regroup_async=False)

    return created


def create_captures_from_files(
    deployment: Deployment, skip_existing=True
) -> list[tuple[SourceImage, GeneratedTestFrame]]:
    assert deployment.data_source is not None
    frame_data = populate_bucket(
        config=deployment.data_source.config,
        subdir=f"deployment_{deployment.pk}",
        skip_existing=skip_existing,
    )

    deployment.sync_captures()
    assert deployment.captures.count() > 0, "Captures were synced, but no files were found."
    group_images_into_events(deployment)

    collection = SourceImageCollection.objects.create(
        project=deployment.project,
        name="Test Source Image Collection",
    )
    collection.images.set(SourceImage.objects.filter(deployment=deployment))

    source_images = SourceImage.objects.filter(deployment=deployment).order_by("timestamp")
    source_images = [img for img in source_images if any(img.path.endswith(frame.filename) for frame in frame_data)]

    assert len(source_images) == len(
        frame_data
    ), f"There are {len(source_images)} source images and {len(frame_data)} frame data items."
    frame_data = sorted(frame_data, key=lambda x: x.timestamp)
    frames_with_images = list(zip(source_images, frame_data))
    for source_image, frame in frames_with_images:
        assert source_image.timestamp == frame.timestamp
        assert source_image.path.endswith(frame.filename)

    return frames_with_images


def create_taxa(project: Project) -> TaxaList:
    taxa_list = TaxaList.objects.create(name="Test Taxa List")
    taxa_list.projects.add(project)
    root, _created = Taxon.objects.get_or_create(name="Lepidoptera", rank=TaxonRank.ORDER.name)
    root.projects.add(project)
    family_taxon, _ = Taxon.objects.get_or_create(name="Nymphalidae", parent=root, rank=TaxonRank.FAMILY.name)
    family_taxon.projects.add(project)
    genus_taxon, _ = Taxon.objects.get_or_create(name="Vanessa", parent=family_taxon, rank=TaxonRank.GENUS.name)
    genus_taxon.projects.add(project)
    for species in ["Vanessa itea", "Vanessa cardui", "Vanessa atalanta"]:
        species_taxa = []
        taxon, _ = Taxon.objects.get_or_create(
            name=species,
            defaults=dict(
                parent=genus_taxon,
                rank=TaxonRank.SPECIES.name,
            ),
        )
        species_taxa.append(taxon)
        taxon.projects.add(project)
    taxa_list.taxa.set([root, family_taxon, genus_taxon] + species_taxa)
    for taxon in taxa_list.taxa.all():
        taxon.projects.add(project)
    #  project.taxa.set([taxa_list.taxa.all()])
    return taxa_list


TEST_TAXA_CSV_DATA = """
id,name,rank,parent_id
1,Lepidoptera,ORDER,
2,Nymphalidae,FAMILY,1
3,Vanessa,GENUS,2
4,Vanessa atalanta,SPECIES,3
5,Vanessa cardui,SPECIES,3
6,Vanessa itea,SPECIES,3
""".strip()


def create_taxa_from_csv(project: Project, csv_data: str = TEST_TAXA_CSV_DATA):
    import csv
    from io import StringIO

    taxa_list = TaxaList.objects.create(name="Test Taxa List")
    taxa_list.projects.add(project)

    def create_taxon(taxon_data: dict, parent=None):
        taxon, _ = Taxon.objects.get_or_create(
            id=taxon_data["id"],
            name=taxon_data["name"],
            rank=taxon_data["rank"],
            parent_id=taxon_data["parent_id"] or None,
        )
        taxon.projects.add(project)
        taxa_list.taxa.add(taxon)
        taxon.save(update_calculated_fields=True)

        return taxon

    reader = csv.DictReader(StringIO(csv_data.strip()))
    for row in reader:
        create_taxon(row)

    return taxa_list


def create_detections(
    source_image: SourceImage,
    bboxes: list[tuple[float, float, float, float]],
):
    for i, bbox in enumerate(bboxes):
        detection = Detection.objects.create(
            source_image=source_image,
            timestamp=source_image.timestamp,
            bbox=bbox,
        )
        assert source_image.deployment
        taxon = Taxon.objects.filter(projects=source_image.deployment.project).order_by("?").first()
        if taxon:
            detection.classifications.create(
                taxon=taxon,
                score=random.randint(70, 98) / 100,
                timestamp=source_image.timestamp,
            )


def create_occurrences_from_frame_data(
    frame_data: list[tuple[SourceImage, GeneratedTestFrame]],
    taxa_list: TaxaList | None = None,
) -> list[Occurrence]:
    def make_identifier(series_id: str, bbox_identifier: str):
        return f"{series_id}_{bbox_identifier}"

    # Create an Occurrence for each series of detections, using the same "identifier"
    occurrences_by_identifier = {}
    for source_image, frame in frame_data:
        assert source_image.event, f"Source image {source_image} has no event"
        for bbox in frame.bounding_boxes:
            identifier = make_identifier(frame.series_id, bbox.identifier)
            if identifier not in occurrences_by_identifier:
                occurrences_by_identifier[identifier] = Occurrence.objects.create(
                    event=source_image.event,
                    deployment=source_image.deployment,
                    project=source_image.project,
                )

    # Group detections by identifier and create a Detection for each with the same Taxon classification
    detections_by_identifier = {}
    for source_image, frame in frame_data:
        for bbox in frame.bounding_boxes:
            identifier = make_identifier(frame.series_id, bbox.identifier)
            detections_by_identifier.setdefault(identifier, []).append((source_image, bbox.bbox))

    algorithm = Algorithm.objects.get(key="random-species-classifier")

    for identifier, detections in detections_by_identifier.items():
        assert source_image.deployment
        if not taxa_list:
            taxon = Taxon.objects.order_by("?").first()
        else:
            taxon = taxa_list.taxa.order_by("?").first()
        assert taxon, f"No taxon found to create classification for detections with identifier {identifier}"
        for source_image, bbox in detections:
            detection = Detection.objects.create(
                source_image=source_image,
                timestamp=source_image.timestamp,
                bbox=bbox,
                occurrence=occurrences_by_identifier[identifier],
            )
            detection.classifications.create(
                taxon=taxon,
                score=random.randint(41, 92) / 100,
                timestamp=datetime.datetime.now(),
                algorithm=algorithm,
            )
            detection.save()

    occurrences = list(occurrences_by_identifier.values())

    # Resave all occurrences to update the best detection and species determination
    for occurrence in occurrences:
        occurrence.save()

    # Resave all source images to update cached properties
    for source_image, _ in frame_data:
        source_image.save()

    logger.info(f"Created {len(occurrences)} occurrences from {len(frame_data)} frames")

    create_detection_images(source_image_ids=[img.pk for img, _ in frame_data])

    return occurrences


def create_occurrences(
    deployment: Deployment,
    num: int = 6,
    taxon: Taxon | None = None,
    determination_score: float = 0.9,
):
    # Get all source images for the deployment that have an event
    source_images = list(SourceImage.objects.filter(deployment=deployment))
    if not source_images:
        raise ValueError("No source images with events found for deployment")

    # Get  a random taxon if not provided
    if not taxon:
        taxa_qs = Taxon.objects.filter(projects=deployment.project)
        count = taxa_qs.count()
        if count == 0:
            raise ValueError("No taxa found for project")
        taxon = taxa_qs[random.randint(0, count - 1)]

    # Create occurrences evenly distributed across all source images
    for i in range(num):
        # Select images in a round-robin fashion
        source_image = source_images[i % len(source_images)]

        detection = Detection.objects.create(
            source_image=source_image,
            timestamp=source_image.timestamp,
            bbox=[0.1, 0.1, 0.2, 0.2],
            path=f"detections/test_detection_{i}.jpg",
        )

        detection.classifications.create(
            taxon=taxon,
            score=determination_score,
            timestamp=datetime.datetime.now(),
        )
        occurrence = detection.associate_new_occurrence()

        # Assert that the occurrence was created and has a detection, event, first_appearance,
        # and species determination
        assert detection.occurrence is not None
        assert detection.occurrence.event is not None
        assert detection.occurrence.first_appearance is not None
        assert occurrence.best_detection is not None
        assert occurrence.best_prediction is not None
        assert occurrence.determination is not None
        assert occurrence.determination_score is not None


def create_complete_test_project():
    with transaction.atomic():
        project, deployment = setup_test_project(reuse=False)
        frame_data = create_captures_from_files(deployment)
        taxa_list = create_taxa(project)
        create_occurrences_from_frame_data(frame_data, taxa_list=taxa_list)
        logger.info(f"Created test project {project}")


def create_local_admin_user():
    from django.core.management import call_command

    logger.info("Creating superuser with the credentials set in environment variables")
    try:
        call_command("createsuperuser", interactive=False)
    except Exception as e:
        logger.error(f"Failed to create superuser: {e}")

    email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "Unknown")
    password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "Unknown")
    logger.info(f"Test user credentials: {email} / {password}")
