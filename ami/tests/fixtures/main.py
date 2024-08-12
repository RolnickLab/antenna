import datetime
import pathlib
import uuid

from ami.main.models import Deployment, Detection, Event, Project, SourceImage, TaxaList, Taxon, TaxonRank


def setup_test_project(reuse=True) -> tuple[Project, Deployment]:
    if reuse:
        project, _ = Project.objects.get_or_create(name="Test Project")
        deployment, _ = Deployment.objects.get_or_create(project=project, name="Test Deployment")
    else:
        short_id = uuid.uuid4().hex[:8]
        project = Project.objects.create(name=f"Test Project {short_id}")
        deployment = Deployment.objects.create(project=project, name=f"Test Deployment {short_id}")
    return project, deployment


def create_captures(
    deployment: Deployment,
    num_nights: int = 3,
    images_per_night: int = 3,
    interval_minutes: int = 10,
    subdir: str = "test",
):
    # Create some images over a few monitoring nights
    first_night = datetime.datetime.now()

    created = []
    for night in range(num_nights):
        for i in range(images_per_night):
            path = pathlib.Path(subdir) / f"{night}_{i}.jpg"
            img = SourceImage.objects.create(
                deployment=deployment,
                timestamp=first_night + datetime.timedelta(days=night, minutes=i * interval_minutes),
                path=path,
            )
            created.append(img)

    return created


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


def create_occurrences(
    deployment: Deployment,
    num: int = 6,
    taxon: Taxon | None = None,
):
    event = Event.objects.filter(deployment=deployment).first()
    if not event:
        raise ValueError("No events found for deployment")

    for i in range(num):
        # Every Occurrence requires a Detection
        source_image = SourceImage.objects.filter(event=event).order_by("?").first()
        if not source_image:
            raise ValueError("No source images found for event")
        taxon = taxon or Taxon.objects.filter(projects=deployment.project).order_by("?").first()
        if not taxon:
            raise ValueError("No taxa found for project")
        detection = Detection.objects.create(
            source_image=source_image,
            timestamp=source_image.timestamp,  # @TODO this should be automatically set to the source image timestamp
        )
        # Could speed this up by creating an Occurrence with a determined taxon directly
        # but this tests more of the code.
        detection.classifications.create(
            taxon=taxon,
            score=0.9,
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
