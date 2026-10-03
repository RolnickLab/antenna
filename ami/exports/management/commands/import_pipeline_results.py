import datetime
import json

import pydantic
from dateutil.parser import parse as parse_date
from django.core.management.base import BaseCommand

from ami.main.models import Classification, Deployment, Detection, Event, Occurrence, Project, SourceImage, Taxon
from ami.ml.models import Algorithm


class IncomingDetection(pydantic.BaseModel):
    id: int
    source_image_id: int
    source_image_path: str
    source_image_width: int
    source_image_height: int
    source_image_filesize: int
    label: str
    score: float
    cropped_image_path: str | None = None
    sequence_id: str | None = None  # This is the Occurrence ID on the ADC side (= detections in a sequence)
    timestamp: datetime.datetime
    detection_algorithm: str | None = None  # Name of the object detection algorithm used
    classification_algorithm: str | None = None  # Classification algorithm used to generate the label & score
    bbox: list[int]  # Bounding box in the format [x_min, y_min, x_max, y_max]


class IncomingOccurrence(pydantic.BaseModel):
    id: str
    label: str
    best_score: float
    start_time: datetime.datetime
    end_time: datetime.datetime
    duration: datetime.timedelta
    deployment: str
    event: str
    num_frames: int
    # cropped_image_path: pathlib.Path
    # source_image_id: int
    examples: list[
        IncomingDetection
    ]  # These are the individual detections with source image data, bounding boxes and predictions
    example_crop: str | None = None
    # detections: list[object]
    # deployment: object
    # captures: list[object]


class Command(BaseCommand):
    r"""Import trap data from a JSON file exported from the AMI data companion.

          occurrences.json

      # CURRENT EXAMPLE JSON STRUCTURE:
      {
      "id":"SEQ-91",
      "label":"Azochis rufidiscalis",
      "best_score":0.4857344627,
      "start_time":"2023-01-25T03:49:59.000",
      "end_time":"2023-01-25T03:49:59.000",
      "duration":"P0DT0H0M0S",
      "deployment":"snapshots",
      "event":"2023-01-24",
      "num_frames":1,
      "examples":[
        {
          "id":91,
          "source_image_id":402,
          "source_image_path":"2023_01_24\/257-20230125034959-snapshot.jpg",
          "source_image_width":4096,
          "source_image_height":2160,
          "source_image_filesize":1276685,
          "label":"Azochis rufidiscalis",
          "score":0.4857344627,
          "cropped_image_path":"\/media\/michael\/ZWEIBEL\/ami-ml-data\/trapdata\/crops\/820709c454b529d5cf44e59fea1f4b5b.jpg",
          "sequence_id":"20230124-SEQ-91",
          "timestamp":"2023-01-25T03:49:59.000",
          "bbox":[
            2191,
            413,
            2568,
            638
          ]
        }
      ],
      "example_crop":null
    },
    {
      "id":"SEQ-86",
      "label":"Sphinx canadensis",
      "best_score":0.4561957121,
      "start_time":"2023-01-24T20:11:59.000",
      "end_time":"2023-01-24T20:11:59.000",
      "duration":"P0DT0H0M0S",
      "deployment":"snapshots",
      "event":"2023-01-24",
      "num_frames":1,
      "examples":[
        {
          "id":86,
          "source_image_id":88,
          "source_image_path":"2023_01_24\/55-20230124201159-snapshot.jpg",
          "source_image_width":4096,
          "source_image_height":2160,
          "source_image_filesize":1013757,
          "label":"Sphinx canadensis",
          "score":0.4561957121,
          "cropped_image_path":"\/media\/michael\/ZWEIBEL\/ami-ml-data\/trapdata\/crops\/839fd6565461939ef946751b87003eda.jpg",
          "sequence_id":"20230124-SEQ-86",
          "timestamp":"2023-01-24T20:11:59.000",
          "bbox":[
            1629,
            0,
            1731,
            25
          ]
        }
      ],
      "example_crop":null
    },
    """

    help = "Import trap data from AMI data manager occurrences.json file"

    def add_arguments(self, parser):
        parser.add_argument("occurrences", type=str)
        parser.add_argument("project_id", type=str, help="Project to import to")

    def handle(self, *args, **options):
        occurrences = json.load(open(options["occurrences"]))
        project_id = options["project_id"]

        project = Project.objects.get(pk=project_id)
        self.stdout.write(self.style.SUCCESS('Importing to project "%s"' % project.name))

        """
        -) Collect all Deployments that need to be created or fetched
        -) Collect all SourceImages that need to be created or fetched
        -) Collect all Occurrences that need to be created or fetched
        -) Create Deployments, linking them to the correct Project
        -) Create SourceImages, linking them to the correct Occurrence and Deployment
        -) Create Occurrences, linking them to the correct Deployment and Project
        -) Generate events (save deployments to trigger event generation)
        -) Create Detections, linking them to the correct Occurrence and SourceImage
        -) Create Classifications, linking them to the correct Detection and Taxon
        -) commit transaction, if transaction is possible
        """

        # Create a fallback algorithm for detections missing algorithm info
        default_classification_algorithm, created = Algorithm.objects.get_or_create(
            name="Unknown classifier from ADC import",
            task_type="classification",
            defaults={
                "description": "Unknown classification model imported from AMI data companion occurrences.json",
                "version": 0,
            },
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS('Created fallback algorithm "%s"' % default_classification_algorithm.name)
            )
        default_detection_algorithm, created = Algorithm.objects.get_or_create(
            name="Unknown object detector from ADC import",
            task_type="localization",
            defaults={
                "description": "Unknown object detection model imported from AMI data companion occurrences.json",
                "version": 0,
            },
        )

        # Process each occurrence from the JSON file
        for occurrence_data in occurrences:
            # Get or create deployment
            deployment, created = Deployment.objects.get_or_create(
                name=occurrence_data["deployment"],
                project=project,
            )
            if created:
                self.stdout.write(self.style.SUCCESS('Successfully created deployment "%s"' % deployment))

            # Get or create taxon for the occurrence
            best_taxon, created = Taxon.objects.get_or_create(name=occurrence_data["label"])
            if created:
                self.stdout.write(self.style.SUCCESS('Successfully created taxon "%s"' % best_taxon))

            # Create occurrence
            occurrence = Occurrence.objects.create(
                event=None,  # will be assigned when events are grouped
                deployment=deployment,
                project=project,
                determination=best_taxon,
                determination_score=occurrence_data["best_score"],
            )
            self.stdout.write(self.style.SUCCESS('Successfully created occurrence "%s"' % occurrence))

            # Process each detection example in the occurrence
            for example in occurrence_data["examples"]:
                try:
                    # Create or get source image
                    image, created = SourceImage.objects.get_or_create(
                        path=example["source_image_path"],
                        deployment=deployment,
                        defaults={
                            "timestamp": parse_date(example["timestamp"]),
                            "event": None,  # will be assigned when events are calculated
                            "project": project,
                            "width": example["source_image_width"],
                            "height": example["source_image_height"],
                            "size": example["source_image_filesize"],
                        },
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS('Successfully created image "%s"' % image))

                except KeyError as e:
                    self.stdout.write(self.style.ERROR('Error creating image - missing field: "%s"' % e))
                    continue

                # Create detection
                detection, created = Detection.objects.get_or_create(
                    occurrence=occurrence,
                    source_image=image,
                    bbox=example["bbox"],
                    defaults={
                        "path": example.get("cropped_image_path"),
                        "timestamp": parse_date(example["timestamp"]),
                    },
                )
                if created:
                    self.stdout.write(self.style.SUCCESS('Successfully created detection "%s"' % detection))

                # Get or create taxon for this specific detection
                detection_taxon, created = Taxon.objects.get_or_create(name=example["label"])
                if created:
                    self.stdout.write(self.style.SUCCESS('Successfully created taxon "%s"' % detection_taxon))

                # Determine which algorithm to use
                algorithm_to_use = default_classification_algorithm
                if example.get("classification_algorithm"):
                    # Try to find an algorithm with this name
                    try:
                        algorithm_to_use = Algorithm.objects.get(name=example["classification_algorithm"])
                    except Algorithm.DoesNotExist:
                        # Create new algorithm if it doesn't exist
                        algorithm_to_use, created = Algorithm.objects.get_or_create(
                            name=example["classification_algorithm"],
                            task_type="classification",
                            defaults={
                                "description": "Algorithm imported from AMI data companion: "
                                f"{example['classification_algorithm']}",
                                "version": 0,
                            },
                        )
                        if created:
                            self.stdout.write(self.style.SUCCESS('Created algorithm "%s"' % algorithm_to_use.name))

                # Create classification
                classification, created = Classification.objects.get_or_create(
                    detection=detection,
                    algorithm=algorithm_to_use,
                    taxon=detection_taxon,
                    defaults={
                        "score": example["score"],
                        "timestamp": parse_date(example["timestamp"]),
                        "terminal": True,
                    },
                )
                if created:
                    self.stdout.write(self.style.SUCCESS('Successfully created classification "%s"' % classification))

        # Regroup images into events for all deployments that were modified
        self.stdout.write(self.style.SUCCESS("Regrouping images into events..."))
        deployments_to_update = Deployment.objects.filter(project=project)
        for deployment in deployments_to_update:
            deployment.save(regroup_async=False)
            self.stdout.write(self.style.SUCCESS('Updated events for deployment "%s"' % deployment))

        # Update event timestamps
        events_updated = 0
        for event in Event.objects.filter(project=project):
            event.save()
            events_updated += 1

        self.stdout.write(self.style.SUCCESS("Updated %d events" % events_updated))
        self.stdout.write(self.style.SUCCESS("Import completed successfully!"))
