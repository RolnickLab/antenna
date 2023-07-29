import datetime
import json

from dateutil.parser import parse as parse_date
from django.core.management.base import BaseCommand, CommandError  # noqa

from ...models import Algorithm, Classification, Deployment, Detection, Event, Occurrence, Project, SourceImage, Taxon


class Command(BaseCommand):
    r"""Import trap data from a JSON file exported from the AMI data companion.

        occurrences.json
    [
    {
      "id":"20220620-SEQ-207259",
      "label":"Baileya ophthalmica",
      "best_score":0.6794486046,
      "start_time":"2022-06-21T09:23:00.000Z",
      "end_time":"2022-06-21T09:23:00.000Z",
      "duration":"P0DT0H0M0S",
      "deployment":"Vermont-Snapshots-Sample",
      "event":{
        "id":19,
        "day":"2022-06-20T00:00:00.000",
        "url":null
      },
      "num_frames":1,
      "examples":[
        {
          "id":207259,
          "source_image_id":15050,
          "source_image_path":"2022_06_21_snapshots\/20220621052300-301-snapshot.jpg",
          "source_image_width":4096,
          "source_image_height":2160,
          "source_image_filesize":1599836,
          "label":"Baileya ophthalmica",
          "score":0.6794486046,
          "cropped_image_path":"exports\/occurrences_images\/20220620-SEQ-207259-963edb524a59504392d4bec06717857a.jpg",
          "sequence_id":"20220620-SEQ-207259",
          "timestamp":"2022-06-21T09:23:00.000Z",
          "bbox":[
            3598,
            1074,
            3821,
            1329
          ]
        }
      ],
      "url":null
    },
        ]
    """

    help = "Import trap data from AMI data manager occurrences.json file"

    def add_arguments(self, parser):
        parser.add_argument("occurrences", type=str)

    def handle(self, *args, **options):
        occurrences = json.load(open(options["occurrences"]))

        project, created = Project.objects.get_or_create(name="Default Project")
        if created:
            self.stdout.write(self.style.SUCCESS('Successfully created project "%s"' % project))
        algorithm, created = Algorithm.objects.get_or_create(name="Latest Model", version="1.0")
        for occurrence in occurrences:
            deployment, created = Deployment.objects.get_or_create(
                name=occurrence["deployment"],
                project=project,
            )
            if created:
                self.stdout.write(self.style.SUCCESS('Successfully created deployment "%s"' % deployment))

            event, created = Event.objects.get_or_create(
                start=parse_date(occurrence["event"]["day"]),
                deployment=deployment,
            )
            if created:
                self.stdout.write(self.style.SUCCESS('Successfully created event "%s"' % event))

            best_taxon, created = Taxon.objects.get_or_create(name=occurrence["label"])
            occ = Occurrence.objects.create(
                event=event,
                deployment=deployment,
                project=project,
                determination=best_taxon,
            )
            self.stdout.write(self.style.SUCCESS('Successfully created occurrence "%s"' % occ))

            for example in occurrence["examples"]:
                try:
                    image, created = SourceImage.objects.get_or_create(
                        path=example["source_image_path"],
                        timestamp=parse_date(example["timestamp"]),
                        event=event,
                        deployment=deployment,
                        width=example["source_image_width"],
                        height=example["source_image_height"],
                        size=example["source_image_filesize"],
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS('Successfully created image "%s"' % image))
                except KeyError as e:
                    self.stdout.write(self.style.ERROR('Error creating image "%s"' % e))
                    image = None

                if image:
                    detection, created = Detection.objects.get_or_create(
                        occurrence=occ,
                        source_image=image,
                        timestamp=parse_date(example["timestamp"]),
                        path=example["cropped_image_path"],
                        bbox=example["bbox"],
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS('Successfully created detection "%s"' % detection))
                else:
                    detection = None

                taxon, created = Taxon.objects.get_or_create(name=example["label"])

                if detection:
                    one_day_later = datetime.timedelta(seconds=60 * 60 * 24)
                    classification, created = Classification.objects.get_or_create(
                        score=example["score"],
                        determination=taxon,
                        detection=detection,
                        type="machine",
                        algorithm=algorithm,
                        timestamp=parse_date(example["timestamp"]) + one_day_later,
                    )
                    if created:
                        self.stdout.write(
                            self.style.SUCCESS('Successfully created classification "%s"' % classification)
                        )

        # Update event start and end times based on the first and last detections
        for event in Event.objects.all():
            event.save()
