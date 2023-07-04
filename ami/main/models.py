import datetime
import textwrap
import urllib.parse
from typing import Final, final  # noqa: F401

from django.db import models
from django.db.models import Q

#: That's how constants should be defined.
_POST_TITLE_MAX_LENGTH: Final = 80
_CLASSIFICATION_TYPES = ("machine", "human", "ground_truth")
_TAXON_RANKS = ("SPECIES", "GENUS", "FAMILY", "ORDER")

# @TODO move to settings & make configurable
_SOURCE_IMAGES_URL_BASE = "https://static.dev.insectai.org/ami-trapdata/vermont/snapshots/"
_CROPS_URL_BASE = "https://static.dev.insectai.org/ami-trapdata/crops"


as_choices = lambda x: [(i, i) for i in x]  # noqa: E731


class BaseModel(models.Model):
    """ """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        """All django models should have this method."""
        if hasattr(self, "name"):
            name = getattr(self, "name") or "Untitled"
            return textwrap.wrap(name, _POST_TITLE_MAX_LENGTH // 4)[0]
        else:
            return f"{self.__class__.__name__} #{self.pk}"

    class Meta:
        abstract = True


@final
class Project(BaseModel):
    """ """

    name = models.CharField(max_length=_POST_TITLE_MAX_LENGTH)
    description = models.TextField()

    # Backreferences for type hinting
    deployments: models.QuerySet["Deployment"]

    def deployments_count(self) -> int:
        return self.deployments.count()

    def taxa(self) -> models.QuerySet["Taxon"]:
        return Taxon.objects.filter(Q(occurrences__project=self)).distinct()

    def taxa_count(self):
        return self.taxa().count()


@final
class Device(BaseModel):
    """Configuration of hardware used to capture images"""

    name = models.CharField(max_length=_POST_TITLE_MAX_LENGTH)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Device Configuration"


@final
class Site(BaseModel):
    """Research site with multiple deployments"""

    name = models.CharField(max_length=_POST_TITLE_MAX_LENGTH)
    description = models.TextField(blank=True)

    deployments: models.QuerySet["Deployment"]

    def deployments_count(self) -> int:
        return self.deployments.count()

    # def boundary(self) -> Optional[models.GeometryField]:
    # @TODO if/when we use GeoDjango
    #     return None

    def boundary_rect(self) -> tuple[float, float, float, float] | None:
        # Get the minumin and maximum latitude and longitude values of all deployments
        # at this research site.
        min_lat, max_lat, min_lon, max_lon = self.deployments.aggregate(
            min_lat=models.Min("latitude"),
            max_lat=models.Max("latitude"),
            min_lon=models.Min("longitude"),
            max_lon=models.Max("longitude"),
        ).values()

        bounds = (min_lat, min_lon, max_lat, max_lon)
        if None in bounds:
            return None
        else:
            return bounds


@final
class Deployment(BaseModel):
    """ """

    name = models.CharField(max_length=_POST_TITLE_MAX_LENGTH)
    description = models.TextField(blank=True)
    data_source = models.TextField(default="s3://bucket-name/prefix", blank=True, max_length=255)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name="deployments")

    research_site = models.ForeignKey(
        Site,
        on_delete=models.SET_NULL,
        null=True,
        related_name="deployments",
    )

    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, related_name="deployments")

    events: models.QuerySet["Event"]
    captures: models.QuerySet["SourceImage"]
    occurrences: models.QuerySet["Occurrence"]

    def events_count(self) -> int:
        return self.events.count()

    def captures_count(self) -> int:
        return self.captures.count()

    def detections_count(self) -> int:
        return Detection.objects.filter(Q(source_image__deployment=self)).count()

    def occurrences_count(self) -> int:
        return self.occurrences.count()

    def taxa(self) -> models.QuerySet["Taxon"]:
        return Taxon.objects.filter(Q(occurrences__deployment=self)).distinct()

    def taxa_count(self) -> int:
        return self.taxa().count()


@final
class Event(BaseModel):
    """A monitoring session"""

    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)

    deployment = models.ForeignKey(Deployment, on_delete=models.SET_NULL, null=True, related_name="events")

    captures: models.QuerySet["SourceImage"]
    occurrences: models.QuerySet["Occurrence"]

    def __str__(self) -> str:
        return f"Event #{self.pk} ({self.date_label()})"

    def day(self) -> datetime.date:
        """
        Consider the start of the event to be the day it occurred on.

        Most overnight monitoring sessions will start in the evening and end the next morning.
        """
        return self.start.date()

    def date_label(self) -> str:
        """
        Format the date range for display.

        If the start and end dates are different, display them as:
        Jan 1-5, 2021
        """
        if self.end and self.end.date() != self.start.date():
            return f"{self.start.strftime('%b %-d')}-{self.end.strftime('%-d, %Y')}"
        else:
            return f"{self.start.strftime('%b %-d, %Y')}"

    def duration(self):
        """Return the duration of the event.

        If the event is still in progress, use the current time as the end time.
        """
        now = datetime.datetime.now(tz=self.start.tzinfo)
        if not self.end:
            return now - self.start
        return self.end - self.start

    def duration_label(self) -> str:
        """Format the duration for display.

        Examples:
        5 minutes
        2 hours 30 min
        2 days 5 hours
        """
        duration = self.duration()
        if duration < datetime.timedelta(hours=1):
            return f"{duration.seconds // 60} minutes"
        if duration < datetime.timedelta(days=1):
            return f"{duration.seconds // 3600} hours {duration.seconds % 3600 // 60} min"
        else:
            return f"{duration.days} days {duration.seconds // 3600} hours"

    def captures_count(self) -> int:
        return self.captures.count()

    def occurrences_count(self) -> int:
        return self.occurrences.count()

    def detections_count(self) -> int:
        return Detection.objects.filter(Q(source_image__event=self)).count()

    def taxa(self) -> models.QuerySet["Taxon"]:
        return Taxon.objects.filter(Q(occurrences__event=self)).distinct()

    def taxa_count(self) -> int:
        return self.taxa().count()

    def example_captures(self, num=5):
        return SourceImage.objects.filter(event=self).order_by("?")[:num]


@final
class StorageSource(BaseModel):
    pass


@final
class SourceImage(BaseModel):
    """A single image captured during a monitoring session"""

    # file = (
    #     models.ImageField(
    #         null=True,
    #         blank=True,
    #         upload_to="source_images",
    #         width_field="width",
    #         height_field="height",
    #     ),
    # )
    path = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(null=True, blank=True)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    size = models.IntegerField(null=True, blank=True)
    md5hash = models.CharField(max_length=32, blank=True)

    deployment = models.ForeignKey(Deployment, on_delete=models.SET_NULL, null=True, related_name="captures")
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, related_name="captures")

    detections: models.QuerySet["Detection"]

    def detections_count(self) -> int:
        # @TODO remove this method and use QuerySet annotation instead
        return self.detections.count()

    def url(self):
        # @TODO use settings or deployment storage base
        # urllib.parse.urljoin(settings.MEDIA_URL, self.path)
        url = urllib.parse.urljoin(_SOURCE_IMAGES_URL_BASE, self.path)
        return url


@final
class ClassificationResult(BaseModel):
    """A classification result from a model"""

    pass


@final
class Classification(BaseModel):
    """The output of a classifier"""

    detection = models.ForeignKey(
        "Detection",
        on_delete=models.SET_NULL,
        null=True,
        related_name="classifications",
    )

    determination = models.ForeignKey("Taxon", on_delete=models.SET_NULL, null=True)
    score = models.FloatField(null=True)
    timestamp = models.DateTimeField()

    softmax_output = models.JSONField(null=True)  # scores for all classes
    raw_output = models.JSONField(null=True)  # raw output from the model

    algorithm = models.ForeignKey(
        "Algorithm",
        on_delete=models.SET_NULL,
        null=True,
    )
    # job = models.CharField(max_length=255, null=True)

    # @TODO maybe ML classification and human classificaions should be separate models?
    type = models.CharField(max_length=255, choices=as_choices(_CLASSIFICATION_TYPES))

    class Meta:
        constraints = [
            # Ensure that the type is one of the allowed values at the database level
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_type_valid",
                check=models.Q(
                    type__in=_CLASSIFICATION_TYPES,
                ),
            ),
        ]


@final
class Algorithm(BaseModel):
    """A machine learning algorithm"""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    version = models.CharField(max_length=255, blank=True)
    url = models.URLField(blank=True)

    classfications: models.QuerySet["Classification"]


@final
class Detection(BaseModel):
    """An object detected in an image"""

    source_image = models.ForeignKey(
        SourceImage,
        on_delete=models.CASCADE,
        related_name="detections",
    )

    bbox = models.JSONField(null=True, blank=True)

    timestamp = models.DateTimeField(null=True, blank=True)

    # file = (
    #     models.ImageField(
    #         null=True,
    #         blank=True,
    #         upload_to="detections",
    #     ),
    # )
    path = models.CharField(max_length=255, blank=True)

    occurrence = models.ForeignKey(
        "Occurrence",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="detections",
    )
    frame_num = models.IntegerField(null=True, blank=True)

    detection_algorithm = models.ForeignKey(
        "Algorithm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    detection_time = models.DateTimeField(null=True, blank=True)
    detection_score = models.FloatField(null=True, blank=True)
    # detection_job = models.ForeignKey(
    #     "Job",
    #     on_delete=models.SET_NULL,
    #     null=True,
    # )

    similarity_vector = models.JSONField(null=True, blank=True)

    classifications: models.QuerySet["Classification"]

    # def bbox(self):
    #     return (
    #         self.bbox_x,
    #         self.bbox_y,
    #         self.bbox_width,
    #         self.bbox_height,
    #     )

    # def bbox_coords(self):
    #     return (
    #         self.bbox_x,
    #         self.bbox_y,
    #         self.bbox_x + self.bbox_width,
    #         self.bbox_y + self.bbox_height,
    #     )

    # def bbox_percent(self):
    #     return (
    #         self.bbox_x / self.source_image.width,
    #         self.bbox_y / self.source_image.height,
    #         self.bbox_width / self.source_image.width,
    #         self.bbox_height / self.source_image.height,
    #     )

    def width(self) -> int | None:
        if self.bbox and len(self.bbox) == 4:
            return self.bbox[2] - self.bbox[0]

    def height(self) -> int | None:
        if self.bbox and len(self.bbox) == 4:
            return self.bbox[3] - self.bbox[1]

    class Meta:
        ordering = [
            "frame_num",
            "timestamp",
        ]

    def best_classification(self):
        classification = (
            self.classifications.order_by("-score")
            .select_related("determination", "determination__name", "score")
            .first()
        )
        if classification and classification.determination:
            return (classification.determination.name, classification.score)
        else:
            return (None, None)

    def url(self):
        # @TODO use settings
        # urllib.parse.urljoin(settings.MEDIA_URL, self.path)
        url = urllib.parse.urljoin(_CROPS_URL_BASE, self.path)
        return url


@final
class Occurrence(BaseModel):
    """An occurrence of a taxon, a sequence of one or more detections"""

    determination = models.ForeignKey("Taxon", on_delete=models.SET_NULL, null=True, related_name="occurrences")
    # determination_score = models.FloatField(null=True, blank=True)

    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, related_name="occurrences")
    deployment = models.ForeignKey(Deployment, on_delete=models.SET_NULL, null=True, related_name="occurrences")
    project = models.ForeignKey("Project", on_delete=models.SET_NULL, null=True, related_name="occurrences")

    detections: models.QuerySet[Detection]

    def detections_count(self):
        # @TODO remove this method and use QuerySet annotation instead
        return self.detections.count()

    def duration(self) -> datetime.timedelta | None:
        first = self.detections.first()
        last = self.detections.last()

        if first and last and first.timestamp and last.timestamp:
            return last.timestamp - first.timestamp
        else:
            return None

    def detection_images(self, limit=5):
        for url in Detection.objects.filter(occurrence=self).values_list("path", flat=True)[:limit]:
            yield urllib.parse.urljoin(_CROPS_URL_BASE, url)

    def determination_score(self) -> float | None:
        return (
            Classification.objects.filter(detection__occurrence=self)
            .order_by("-created_at")
            .aggregate(models.Max("score"))["score__max"]
        )

    def determination_algorithm(self) -> Algorithm | None:
        return Algorithm.objects.filter(classification__detection__occurrence=self).first()


@final
class Taxon(BaseModel):
    """A taxonomic classification"""

    name = models.CharField(max_length=255)
    rank = models.CharField(max_length=255, choices=as_choices(_TAXON_RANKS))
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, related_name="direct_children")
    parents = models.ManyToManyField("self", related_name="children", symmetrical=False)

    direct_children: models.QuerySet["Taxon"]
    children: models.QuerySet["Taxon"]
    occurrences: models.QuerySet[Occurrence]

    def num_direct_children(self) -> int:
        return self.direct_children.count()

    def num_children_recursive(self) -> int:
        # @TODO how to do this with a single query?
        return self.children.count() + sum(child.num_children_recursive() for child in self.children.all())

    def occurrences_count(self) -> int:
        return self.occurrences.count()

    def detections_count(self) -> int:
        return Detection.objects.filter(occurrence__determination=self).count()

    def latest_occurrence(self) -> Occurrence | None:
        return self.occurrences.order_by("-created_at").first()

    def latest_detection(self) -> Detection | None:
        return Detection.objects.filter(occurrence__determination=self).order_by("-created_at").first()

    class Meta:
        ordering = ["parent__name", "name"]
        verbose_name_plural = "Taxa"


@final
class TaxaListEntry(BaseModel):
    """A taxon in a checklist"""

    taxon = models.ForeignKey(Taxon, on_delete=models.CASCADE)
    list = models.ForeignKey("TaxaList", on_delete=models.CASCADE)
    ordering = models.IntegerField()

    class Meta:
        ordering = ["ordering"]


@final
class TaxaList(BaseModel):
    """A checklist of taxa"""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    taxa = models.ManyToManyField(Taxon, related_name="lists", through="TaxaListEntry")


@final
class BlogPost(BaseModel):
    """
    This model is used just as an example.

    With it we show how one can:
    - Use fixtures and factories
    - Use migrations testing

    """

    title = models.CharField(max_length=_POST_TITLE_MAX_LENGTH)
    body = models.TextField()

    class Meta:
        verbose_name = "Blog Post"  # You can probably use `gettext` for this
        verbose_name_plural = "Blog Posts"

    def __str__(self) -> str:
        """All django models should have this method."""
        return textwrap.wrap(self.title, _POST_TITLE_MAX_LENGTH // 4)[0]
