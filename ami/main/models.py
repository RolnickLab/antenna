import collections
import datetime
import functools
import hashlib
import logging
import textwrap
import time
import typing
import urllib.parse
from typing import Final, final  # noqa: F401

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models
from django.db.models import Q
from django.db.models.fields.files import ImageFieldFile
from django.db.models.signals import pre_delete
from django.dispatch import receiver

import ami.tasks
import ami.utils
from ami.base.models import BaseModel
from ami.main import charts
from ami.users.models import User
from ami.utils.schemas import OrderedEnum

logger = logging.getLogger(__name__)

# Constants
_POST_TITLE_MAX_LENGTH: Final = 80


class TaxonRank(OrderedEnum):
    ORDER = "Order"
    SUPERFAMILY = "Superfamily"
    FAMILY = "Family"
    SUBFAMILY = "Subfamily"
    TRIBE = "Tribe"
    SUBTRIBE = "Subtribe"
    GENUS = "Genus"
    SPECIES = "Species"
    UNKNOWN = "Unknown"


DEFAULT_RANKS = sorted(
    [
        TaxonRank.ORDER,
        TaxonRank.FAMILY,
        TaxonRank.SUBFAMILY,
        TaxonRank.TRIBE,
        TaxonRank.GENUS,
        TaxonRank.SPECIES,
    ]
)


# @TODO move to settings & make configurable
_SOURCE_IMAGES_URL_BASE = "https://static.dev.insectai.org/ami-trapdata/vermont/snapshots/"
_CROPS_URL_BASE = "https://static.dev.insectai.org/ami-trapdata/crops"


def get_media_url(path: str) -> str:
    """
    If path is a full URL, return it as-is.
    Otherwise, join it with the MEDIA_URL setting.
    """
    # @TODO use settings
    # urllib.parse.urljoin(settings.MEDIA_URL, self.path)
    if path.startswith("http"):
        url = path
    else:
        url = urllib.parse.urljoin(_CROPS_URL_BASE, path.lstrip("/"))
    return url


as_choices = lambda x: [(i, i) for i in x]  # noqa: E731


def create_default_device(project: "Project") -> "Device":
    """Create a default device for a project."""
    device, _created = Device.objects.get_or_create(name="Default device", project=project)
    logger.info(f"Created default device for project {project}")
    return device


def create_default_research_site(project: "Project") -> "Site":
    """Create a default research site for a project."""
    site, _created = Site.objects.get_or_create(name="Default site", project=project)
    logger.info(f"Created default research site for project {project}")
    return site


@final
class Project(BaseModel):
    """ """

    name = models.CharField(max_length=_POST_TITLE_MAX_LENGTH)
    description = models.TextField()
    image = models.ImageField(upload_to="projects", blank=True, null=True)

    # Backreferences for type hinting
    deployments: models.QuerySet["Deployment"]
    events: models.QuerySet["Event"]
    occurrences: models.QuerySet["Occurrence"]
    taxa: models.QuerySet["Taxon"]
    taxa_lists: models.QuerySet["TaxaList"]

    active = models.BooleanField(default=True)
    priority = models.IntegerField(default=1)

    devices: models.QuerySet["Device"]
    sites: models.QuerySet["Site"]

    def deployments_count(self) -> int:
        return self.deployments.count()

    def taxa_count(self):
        return self.taxa.all().count()

    def summary_data(self):
        """
        Data prepared for rendering charts with plotly.js on the overview page.
        """

        plots = []

        plots.append(charts.captures_per_hour(project_pk=self.pk))
        if self.occurrences.exists():
            plots.append(charts.detections_per_hour(project_pk=self.pk))
            plots.append(charts.occurrences_accumulated(project_pk=self.pk))
        else:
            plots.append(charts.events_per_month(project_pk=self.pk))
            # plots.append(charts.captures_per_month(project_pk=self.pk))

        return plots

    def create_related_defaults(self):
        """Create default device, and other related models for this project if they don't exist."""
        if not self.devices.exists():
            create_default_device(project=self)
        if not self.sites.exists():
            create_default_research_site(project=self)

    def save(self, *args, **kwargs):
        new_project = bool(self._state.adding)
        super().save(*args, **kwargs)
        if new_project:
            logger.info(f"Created new project {self}")
            self.create_related_defaults()

    class Meta:
        ordering = ["-priority", "created_at"]


@final
class Device(BaseModel):
    """
    Configuration of hardware used to capture images.

    If project is null then this is a public device that can be used by any project.
    """

    name = models.CharField(max_length=_POST_TITLE_MAX_LENGTH)
    description = models.TextField(blank=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name="devices")

    deployments: models.QuerySet["Deployment"]

    class Meta:
        verbose_name = "Device Configuration"


@final
class Site(BaseModel):
    """Research site with multiple deployments"""

    name = models.CharField(max_length=_POST_TITLE_MAX_LENGTH)
    description = models.TextField(blank=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name="sites")

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

    class Meta:
        verbose_name = "Research Site"


@final
class DeploymentManager(models.Manager):
    """
    Custom manager that adds counts of related objects to the default queryset.
    """

    def get_queryset(self):
        return (
            super().get_queryset()
            # Add any common annotations or optimizations here
        )


def _create_source_image_for_sync(
    deployment: "Deployment",
    obj: ami.utils.s3.ObjectTypeDef,
) -> typing.Union["SourceImage", None]:
    assert "Key" in obj, f"File in object store response has no Key: {obj}"

    source_image = SourceImage(
        deployment=deployment,
        path=obj["Key"],
        last_modified=obj.get("LastModified"),
        size=obj.get("Size"),
        checksum=obj.get("ETag", "").strip('"'),
        checksum_algorithm=obj.get("ChecksumAlgorithm"),
    )
    logger.debug(f"Preparing to create or update SourceImage {source_image.path}")
    source_image.update_calculated_fields()
    return source_image


def _insert_or_update_batch_for_sync(
    deployment: "Deployment",
    source_images: list["SourceImage"],
    total_files: int,
    total_size: int,
    sql_batch_size=500,
    regroup_events_per_batch=False,
):
    logger.info(f"Bulk inserting or updating batch of {len(source_images)} SourceImages")
    try:
        SourceImage.objects.bulk_create(
            source_images,
            batch_size=sql_batch_size,
            update_conflicts=True,
            unique_fields=["deployment", "path"],  # type: ignore
            update_fields=["last_modified", "size", "checksum", "checksum_algorithm"],
        )
    except IntegrityError as e:
        logger.error(f"Error bulk inserting batch of SourceImages: {e}")

    if total_files > (deployment.data_source_total_files or 0):
        deployment.data_source_total_files = total_files
    if total_size > (deployment.data_source_total_size or 0):
        deployment.data_source_total_size = total_size
    deployment.data_source_last_checked = datetime.datetime.now()

    if regroup_events_per_batch:
        group_images_into_events(deployment)

    deployment.save(update_calculated_fields=False)


def _compare_totals_for_sync(deployment: "Deployment", total_files_found: int):
    # @TODO compare total_files to the number of SourceImages for this deployment
    existing_file_count = SourceImage.objects.filter(deployment=deployment).count()
    delta = abs(existing_file_count - total_files_found)
    if delta > 0:
        logger.warning(
            f"Deployment '{deployment}' has {existing_file_count} SourceImages "
            f"but the data source has {total_files_found} files "
            f"(+- {delta})"
        )


@final
class Deployment(BaseModel):
    """
    Class that describes a deployment of a device (camera & hardware) at a research site.
    """

    name = models.CharField(max_length=_POST_TITLE_MAX_LENGTH)
    description = models.TextField(blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    image = models.ImageField(upload_to="deployments", blank=True, null=True)

    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name="deployments")

    # @TODO consider sharing only the "data source auth/config" then a one-to-one config for each deployment
    data_source = models.ForeignKey(
        "S3StorageSource", on_delete=models.SET_NULL, null=True, blank=True, related_name="deployments"
    )

    # Precalculated values from the data source
    data_source_total_files = models.IntegerField(blank=True, null=True)
    data_source_total_size = models.BigIntegerField(blank=True, null=True)
    data_source_subdir = models.CharField(max_length=255, blank=True, null=True)
    data_source_regex = models.CharField(max_length=255, blank=True, null=True)
    data_source_last_checked = models.DateTimeField(blank=True, null=True)
    # data_source_start_date = models.DateTimeField(blank=True, null=True)
    # data_source_end_date = models.DateTimeField(blank=True, null=True)
    # data_source_last_check_duration = models.DurationField(blank=True, null=True)
    # data_source_last_check_status = models.CharField(max_length=255, blank=True, null=True)
    # data_source_last_check_notes = models.TextField(max_length=255, blank=True, null=True)

    # Precaclulated values
    events_count = models.IntegerField(blank=True, null=True)
    occurrences_count = models.IntegerField(blank=True, null=True)
    captures_count = models.IntegerField(blank=True, null=True)
    detections_count = models.IntegerField(blank=True, null=True)
    taxa_count = models.IntegerField(blank=True, null=True)
    first_capture_timestamp = models.DateTimeField(blank=True, null=True)
    last_capture_timestamp = models.DateTimeField(blank=True, null=True)

    research_site = models.ForeignKey(
        Site,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deployments",
    )

    device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deployments",
    )

    events: models.QuerySet["Event"]
    captures: models.QuerySet["SourceImage"]
    occurrences: models.QuerySet["Occurrence"]

    objects = DeploymentManager()

    class Meta:
        ordering = ["name"]

    def taxa(self) -> models.QuerySet["Taxon"]:
        return Taxon.objects.filter(Q(occurrences__deployment=self)).distinct()

    def example_captures(self, num=10) -> models.QuerySet["SourceImage"]:
        return SourceImage.objects.filter(deployment=self).order_by("-size")[:num]

    def capture_images(self, num=5) -> list[str]:
        return [c.url() for c in self.example_captures(num)]

    def first_capture(self) -> typing.Optional["SourceImage"]:
        return SourceImage.objects.filter(deployment=self).order_by("timestamp").first()

    def last_capture(self) -> typing.Optional["SourceImage"]:
        return SourceImage.objects.filter(deployment=self).order_by("timestamp").last()

    def get_first_and_last_timestamps(self) -> tuple[datetime.datetime, datetime.datetime]:
        # Retrieve the timestamps of the first and last capture in a single query
        first, last = (
            SourceImage.objects.filter(deployment=self)
            .aggregate(first=models.Min("timestamp"), last=models.Max("timestamp"))
            .values()
        )
        return (first, last)

    def first_date(self) -> datetime.date | None:
        return self.first_capture_timestamp.date() if self.first_capture_timestamp else None

    def last_date(self) -> datetime.date | None:
        return self.last_capture_timestamp.date() if self.last_capture_timestamp else None

    def data_source_uri(self) -> str | None:
        if self.data_source:
            uri = self.data_source.uri().rstrip("/")
            if self.data_source_subdir:
                uri = f"{uri}/{self.data_source_subdir.strip('/')}/"
            if self.data_source_regex:
                uri = f"{uri}?regex={self.data_source_regex}"
        else:
            uri = None
        return uri

    def sync_captures(self, batch_size=1000, regroup_events_per_batch=False) -> int:
        """Import images from the deployment's data source"""

        deployment = self
        assert deployment.data_source, f"Deployment {deployment.name} has no data source configured"

        s3_config = deployment.data_source.config
        total_size = 0
        total_files = 0
        source_images = []
        django_batch_size = batch_size
        sql_batch_size = 1000

        for obj in ami.utils.s3.list_files_paginated(
            s3_config,
            subdir=self.data_source_subdir,
            regex_filter=self.data_source_regex,
        ):
            source_image = _create_source_image_for_sync(deployment, obj)
            if source_image:
                total_files += 1
                total_size += obj.get("Size", 0)
                source_images.append(source_image)

            if len(source_images) >= django_batch_size:
                _insert_or_update_batch_for_sync(
                    deployment, source_images, total_files, total_size, sql_batch_size, regroup_events_per_batch
                )
                source_images = []

        if source_images:
            # Insert/update the last batch
            _insert_or_update_batch_for_sync(
                deployment, source_images, total_files, total_size, sql_batch_size, regroup_events_per_batch
            )

        _compare_totals_for_sync(deployment, total_files)

        # @TODO decide if we should delete SourceImages that are no longer in the data source
        self.save()

        return total_files

    def update_children(self):
        """
        Update all attribute on all child objects that should be equal to their deployment values.

        e.g. Events, Occurrences, SourceImages must belong to same project as their deployment. But
        they have their own copy of that attribute to reduce the number of joins required to query them.
        """

        # All the child models that have a foreign key to project
        child_models = [
            "Event",
            "Occurrence",
            "SourceImage",
        ]
        for model_name in child_models:
            model = apps.get_model("main", model_name)
            project_values = set(model.objects.filter(deployment=self).values_list("project", flat=True).distinct())
            if len(project_values) > 1:
                logger.warning(
                    f"Deployment {self} has alternate projects set on {model_name} "
                    f"objects: {project_values}. Updating them!"
                )
            model.objects.filter(deployment=self).exclude(project=self.project).update(project=self.project)

    def update_calculated_fields(self, save=False):
        """Update calculated fields on the deployment."""

        self.data_source_total_files = self.captures.count()
        self.data_source_total_size = self.captures.aggregate(total_size=models.Sum("size")).get("total_size")

        self.events_count = self.events.count()
        self.captures_count = self.data_source_total_files or self.captures.count()
        self.detections_count = Detection.objects.filter(Q(source_image__deployment=self)).count()
        self.occurrences_count = (
            self.occurrences.filter(
                determination_score__gte=settings.DEFAULT_CONFIDENCE_THRESHOLD,
                event__isnull=False,
            )
            .distinct()
            .count()
        )
        self.taxa_count = (
            Taxon.objects.filter(
                occurrences__deployment=self,
                occurrences__determination_score__gte=settings.DEFAULT_CONFIDENCE_THRESHOLD,
                occurrences__event__isnull=False,
            )
            .distinct()
            .count()
        )

        self.first_capture_timestamp, self.last_capture_timestamp = self.get_first_and_last_timestamps()

        if save:
            self.save(update_calculated_fields=False)

    def save(self, update_calculated_fields=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.pk and update_calculated_fields:
            self.update_calculated_fields(save=True)
            if self.project:
                self.update_children()
                # @TODO this isn't working as a background task
                # ami.tasks.model_task.delay("Project", self.project.pk, "update_children_project")
            # @TODO Use "dirty" flag strategy to only update when needed
            ami.tasks.regroup_events.delay(self.pk)


@final
class Event(BaseModel):
    """A monitoring session"""

    group_by = models.CharField(
        max_length=255,
        db_index=True,
        help_text=(
            "A unique identifier for this event, used to group images into events. "
            "This allows images to be prepended or appended to an existing event. "
            "The default value is the day the event started, in the format YYYY-MM-DD. "
            "However images could also be grouped by camera settings, image dimensions, hour of day, "
            "or a random sample."
        ),
    )

    start = models.DateTimeField(db_index=True, help_text="The timestamp of the first image in the event.")
    end = models.DateTimeField(null=True, blank=True, help_text="The timestamp of the last image in the event.")

    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name="events")
    deployment = models.ForeignKey(Deployment, on_delete=models.SET_NULL, null=True, related_name="events")

    captures: models.QuerySet["SourceImage"]
    occurrences: models.QuerySet["Occurrence"]

    class Meta:
        ordering = ["start"]
        indexes = [
            models.Index(fields=["group_by"]),
            models.Index(fields=["start"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["deployment", "group_by"], name="unique_event"),
        ]

    def __str__(self) -> str:
        return f"{self.start.strftime('%A')}, {self.date_label()}"

    def name(self) -> str:
        return str(self)

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
            return f"{self.start.strftime('%b %-d')}-{self.end.strftime('%-d %Y')}"
        else:
            return f"{self.start.strftime('%b %-d %Y')}"

    def duration(self):
        """Return the duration of the event.

        If the event is still in progress, use the current time as the end time.
        """
        now = datetime.datetime.now(tz=self.start.tzinfo)
        if not self.end:
            return now - self.start
        return self.end - self.start

    def duration_label(self) -> str:
        """
        Format the duration for display.

        If duration was populated by a query annotation, use that
        otherwise call the duration() method to calculate it.
        """
        duration = self.duration() if callable(self.duration) else self.duration
        return ami.utils.dates.format_timedelta(duration)

    # These are now loaded with annotations in EventViewSet
    # But the serializer complains if they're not defined here.
    def captures_count(self) -> int | None:
        # return self.captures.distinct().count()
        return None

    def occurrences_count(self, classification_threshold: int | None = None) -> int | None:
        return (
            self.occurrences.distinct()
            .filter(determination_score__gte=classification_threshold or settings.DEFAULT_CONFIDENCE_THRESHOLD)
            .count()
        )

    def detections_count(self) -> int | None:
        # return Detection.objects.filter(Q(source_image__event=self)).count()
        return None

    def stats(self) -> dict[str, int | None]:
        return (
            SourceImage.objects.filter(event=self)
            .annotate(count=models.Count("detections"))
            .aggregate(
                detections_max_count=models.Max("count"),
                detections_min_count=models.Min("count"),
                # detections_avg_count=models.Avg("count"),
            )
        )

    def taxa_count(self, classification_threshold: int | None = None) -> int:
        return self.taxa(classification_threshold).count()

    def taxa(self, classification_threshold: int | None = None) -> models.QuerySet["Taxon"]:
        return Taxon.objects.filter(
            Q(occurrences__event=self),
            occurrences__determination_score__gte=classification_threshold or settings.DEFAULT_CONFIDENCE_THRESHOLD,
        ).distinct()

    def example_captures(self, num=5):
        return SourceImage.objects.filter(event=self).order_by("-size")[:num]

    def first_capture(self):
        return SourceImage.objects.filter(event=self).order_by("timestamp").first()

    def summary_data(self):
        """
        Data prepared for rendering charts with plotly.js
        """
        plots = []

        plots.append(charts.event_detections_per_hour(event_pk=self.pk))
        plots.append(charts.event_top_taxa(event_pk=self.pk))

        return plots

    def update_calculated_fields(self, save=False):
        if not self.group_by and self.start:
            # If no group_by is set, use the start "day"
            self.group_by = self.start.date()

        if not self.project and self.deployment:
            self.project = self.deployment.project

        if self.pk is not None:
            # Can only update start and end times if this is an update to an existing event
            first = self.captures.order_by("timestamp").values("timestamp").first()
            last = self.captures.order_by("-timestamp").values("timestamp").first()
            if first:
                self.start = first["timestamp"]
            if last:
                self.end = last["timestamp"]

        if save:
            self.save(update_calculated_fields=False)

    def save(self, update_calculated_fields=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if update_calculated_fields:
            self.update_calculated_fields(save=True)


def group_images_into_events(
    deployment: Deployment, max_time_gap=datetime.timedelta(minutes=120), delete_empty=True
) -> list[Event]:
    # Log a warning if multiple SourceImages have the same timestamp
    dupes = (
        SourceImage.objects.filter(deployment=deployment)
        .values("timestamp")
        .annotate(count=models.Count("id"))
        .filter(count__gt=1)
        .exclude(timestamp=None)
    )
    if dupes.count():
        values = "\n".join(
            [f'{d.strftime("%Y-%m-%d %H:%M:%S")} x{c}' for d, c in dupes.values_list("timestamp", "count")]
        )
        logger.warning(
            f"Found multiple images with the same timestamp in deployment '{deployment}':\n "
            f"{values}\n"
            f"Only one image will be used for each timestamp for each event."
        )

    image_timestamps = list(
        SourceImage.objects.filter(deployment=deployment)
        .exclude(timestamp=None)
        .values_list("timestamp", flat=True)
        .order_by("timestamp")
        .distinct()
    )

    timestamp_groups = ami.utils.dates.group_datetimes_by_gap(image_timestamps, max_time_gap)
    # @TODO this event grouping needs testing. Still getting events over 24 hours
    # timestamp_groups = ami.utils.dates.group_datetimes_by_shifted_day(image_timestamps)

    events = []
    for group in timestamp_groups:
        if not len(group):
            continue

        start_date = group[0]
        end_date = group[-1]

        # Print debugging info about groups
        delta = end_date - start_date
        hours = round(delta.seconds / 60 / 60, 1)
        logger.debug(
            f"Found session starting at {start_date} with {len(group)} images that ran for {hours} hours.\n"
            f"From {start_date.strftime('%c')} to {end_date.strftime('%c')}."
        )

        # Creating events & assigning images
        group_by = start_date.date()
        event, _ = Event.objects.get_or_create(
            deployment=deployment,
            group_by=group_by,
            defaults={"start": start_date, "end": end_date},
        )
        events.append(event)
        SourceImage.objects.filter(deployment=deployment, timestamp__in=group).update(event=event)
        event.save()  # Update start and end times and other cached fields
        logger.info(
            f"Created/updated event {event} with {len(group)} images for deployment {deployment}. "
            f"Duration: {event.duration_label()}"
        )

    if delete_empty:
        delete_empty_events()

    for event in events:
        # Set the width and height of all images in each event based on the first image
        set_dimensions_for_collection(event)

    events_over_24_hours = Event.objects.filter(
        deployment=deployment, start__lt=models.F("end") - datetime.timedelta(days=1)
    )
    if events_over_24_hours.count():
        logger.warning(f"Found {events_over_24_hours.count()} events over 24 hours in deployment {deployment}. ")
    events_starting_before_noon = Event.objects.filter(
        deployment=deployment, start__lt=models.F("start") + datetime.timedelta(hours=12)
    )
    if events_starting_before_noon.count():
        logger.warning(
            f"Found {events_starting_before_noon.count()} events starting before noon in deployment {deployment}. "
        )

    return events


def delete_empty_events(dry_run=False):
    """
    Delete events that have no images, occurrences or other related records.
    """

    # @TODO Search all models that have a foreign key to Event
    # related_models = [
    #     f.related_model
    #     for f in Event._meta.get_fields()
    #     if f.one_to_many or f.one_to_one or (f.many_to_many and f.auto_created)
    # ]

    events = Event.objects.annotate(num_images=models.Count("captures")).filter(num_images=0)
    events = events.annotate(num_occurrences=models.Count("occurrences")).filter(num_occurrences=0)

    if dry_run:
        for event in events:
            logger.debug(f"Would delete event {event} (dry run)")
    else:
        logger.info(f"Deleting {events.count()} empty events")
        events.delete()


def sample_events(deployment: Deployment, day_interval: int = 3) -> typing.Generator[Event, None, None]:
    """
    Return a sample of events from the deployment, evenly spaced apart by day_interval.
    """

    last_event = None
    for event in Event.objects.filter(deployment=deployment).order_by("start"):
        if not last_event:
            yield event
            last_event = event
        else:
            delta = event.start - last_event.start
            if delta.days >= day_interval:
                yield event
                last_event = event


@final
class S3StorageSource(BaseModel):
    """
    Per-deployment configuration for an S3 bucket.
    """

    name = models.CharField(max_length=255)
    bucket = models.CharField(max_length=255)
    prefix = models.CharField(max_length=255, blank=True)
    access_key = models.TextField()
    secret_key = models.TextField()
    endpoint_url = models.CharField(max_length=255, blank=True, null=True)
    public_base_url = models.CharField(max_length=255, blank=True)
    total_size = models.BigIntegerField(null=True, blank=True)
    total_files = models.BigIntegerField(null=True, blank=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    # last_check_duration = models.DurationField(null=True, blank=True)
    # use_signed_urls = models.BooleanField(default=False)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name="storage_sources")

    deployments: models.QuerySet["Deployment"]

    @property
    def config(self):
        return ami.utils.s3.S3Config(
            bucket_name=self.bucket,
            prefix=self.prefix,
            access_key_id=self.access_key,
            secret_access_key=self.secret_key,
            endpoint_url=self.endpoint_url,
            public_base_url=self.public_base_url,
        )

    def list_files(self, limit=None):
        """Recursively list files in the bucket/prefix."""

        return ami.utils.s3.list_files_paginated(self.config)

    def count_files(self):
        """Count & save the number of files in the bucket/prefix."""

        count = ami.utils.s3.count_files_paginated(self.config)
        self.total_files = count
        self.save()
        return count

    def calculate_size(self):
        """Calculate the total size and count of all files in the bucket/prefix."""

        sizes = [obj["Size"] for obj in self.list_files()]  # type: ignore
        size = sum(sizes)
        count = len(sizes)
        self.total_size = size
        self.total_files = count
        self.save()
        return size

    def uri(self, path: str | None = None):
        """Return the full URI for the given path."""

        full_path = "/".join(str(part).strip("/") for part in [self.bucket, self.prefix, path] if part)
        return f"s3://{full_path}"

    def public_url(self, path: str):
        """Return the public URL for the given path."""

        return ami.utils.s3.public_url(self.config, path)

    def save(self, *args, **kwargs):
        # If public_base_url has changed, update the urls for all source images
        if self.pk:
            old = S3StorageSource.objects.get(pk=self.pk)
            if old.public_base_url != self.public_base_url:
                for deployment in self.deployments.all():
                    ami.tasks.update_public_urls.delay(deployment.pk, self.public_base_url)
        super().save(*args, **kwargs)


def validate_filename_timestamp(filename: str) -> None:
    # Ensure filename has a timestamp
    timestamp = ami.utils.dates.get_image_timestamp_from_filename(filename)
    if not timestamp:
        raise ValidationError("Filename must contain a timestamp in the format YYYYMMDDHHMMSS")


def _create_source_image_from_upload(image: ImageFieldFile, deployment: Deployment, request=None) -> "SourceImage":
    """Create a complete SourceImage from an uploaded file."""
    # md5 checksum from file
    checksum = hashlib.md5(image.read()).hexdigest()
    checksum_algorithm = "md5"

    # get full public media url of image:
    if request:
        base_url = request.build_absolute_uri(settings.MEDIA_URL)
    else:
        base_url = settings.MEDIA_URL

    source_image = SourceImage(
        path=image.name,  # Includes relative path from MEDIA_ROOT
        public_base_url=base_url,  # @TODO how to merge this with the data source?
        project=deployment.project,
        deployment=deployment,
        timestamp=None,  # Will be calculated from filename or EXIF data on save
        event=None,  # Will be assigned when the image is grouped into events
        size=image.size,
        checksum=checksum,
        checksum_algorithm=checksum_algorithm,
        width=image.width,
        height=image.height,
        test_image=True,
        uploaded_by=request.user if request else None,
    )
    source_image.save()
    return source_image


def upload_to_with_deployment(instance, filename: str) -> str:
    """Nest uploads under subdir for a deployment."""
    return f"example_captures/{instance.deployment.pk}/{filename}"


@final
class SourceImageUpload(BaseModel):
    """
    A manually uploaded image that has not yet been imported.

    The SourceImageViewSet will create a SourceImage from the uploaded file and delete the upload.
    """

    image = models.ImageField(upload_to=upload_to_with_deployment, validators=[validate_filename_timestamp])
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE)
    source_image = models.OneToOneField(
        "SourceImage", on_delete=models.CASCADE, null=True, blank=True, related_name="upload"
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # @TODO Use a "dirty" flag to mark the deployment as having new uploads, needs refresh
        self.deployment.save()


@receiver(pre_delete, sender=SourceImageUpload)
def delete_source_image(sender, instance, **kwargs):
    """
    A SourceImageUpload are automatically deleted when deleting a SourceImage because of the CASCADE setting.
    However the SourceImage needs to be deleted using a signal when deleting a SourceImageUpload.
    """
    if instance.source_image:
        # Disconnect the SourceImage from the upload to prevent recursion error
        source_image = instance.source_image
        instance.source_image = None
        instance.save()
        source_image.delete()
    # @TODO Use a "dirty" flag to mark the deployment as having new uploads, needs refresh
    instance.deployment.save()


@final
class SourceImage(BaseModel):
    """A single image captured during a monitoring session"""

    path = models.CharField(max_length=255, blank=True)
    public_base_url = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(null=True, blank=True, db_index=True)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    size = models.BigIntegerField(null=True, blank=True)
    last_modified = models.DateTimeField(null=True, blank=True)
    checksum = models.CharField(max_length=255, blank=True, null=True)
    checksum_algorithm = models.CharField(max_length=255, blank=True, null=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    test_image = models.BooleanField(default=False)
    detections_count = models.IntegerField(null=True, blank=True)

    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name="captures")
    deployment = models.ForeignKey(Deployment, on_delete=models.SET_NULL, null=True, related_name="captures")
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, related_name="captures", db_index=True)

    detections: models.QuerySet["Detection"]
    collections: models.QuerySet["SourceImageCollection"]

    def __str__(self) -> str:
        return f"{self.__class__.__name__} #{self.pk} {self.path}"

    def public_url(self) -> str:
        """
        Return the public URL for this image.

        The base URL is determined by the deployment's data source and is cached
        on the source image. If the deployment's data source changes, the URLs
        for all source images will be updated.

        @TODO use signed URLs if necessary.
        @TODO add support for thumbnail URLs here?
        @TODO consider if we ever need to access the original image directly!
        """
        return urllib.parse.urljoin(self.public_base_url or "/", self.path.lstrip("/"))

    # backwards compatibility
    url = public_url

    def get_detections_count(self) -> int:
        return self.detections.distinct().count()

    def get_base_url(self) -> str:
        """
        Determine the public URL from the deployment's data source.

        If there is no data source, return a relative URL.
        """
        if self.deployment and self.deployment.data_source and self.deployment.data_source.public_base_url:
            return self.deployment.data_source.public_base_url
        else:
            return "/"

    def extract_timestamp(self) -> datetime.datetime | None:
        """
        Extract a timestamp from the filename or EXIF data
        """
        # @TODO use EXIF data if necessary (use methods in AMI data companion repo)
        timestamp = ami.utils.dates.get_image_timestamp_from_filename(self.path)
        if not timestamp:
            # timestamp = ami.utils.dates.get_image_timestamp_from_exif(self.path)
            msg = f"No timestamp could be extracted from the filename or EXIF data of {self.path}"
            logger.error(msg)
        return timestamp

    def get_dimensions(self) -> tuple[int | None, int | None]:
        """Calculate the width and height of the original image."""
        if self.path and self.deployment and self.deployment.data_source:
            config = self.deployment.data_source.config
            try:
                img = ami.utils.s3.read_image(config=config, key=self.path)
            except Exception as e:
                logger.error(f"Could not determine image dimensions for {self.path}: {e}")
            else:
                self.width, self.height = img.size
                self.save()
                return self.width, self.height
        return None, None

    def update_calculated_fields(self, save=False):
        if self.path and not self.timestamp:
            self.timestamp = self.extract_timestamp()
        if self.path and not self.public_base_url:
            self.public_base_url = self.get_base_url()
        if not self.project and self.deployment:
            self.project = self.deployment.project
        if self.pk is not None:
            self.detections_count = self.get_detections_count()
        if save:
            self.save(update_calculated_fields=False)

    def save(self, update_calculated_fields=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if update_calculated_fields:
            self.update_calculated_fields(save=True)

    class Meta:
        ordering = ("deployment", "event", "timestamp")

        # Add two "unique together" constraints to prevent duplicate images
        constraints = [
            # deployment + path (only one image per deployment with a given file path)
            models.UniqueConstraint(fields=["deployment", "path"], name="unique_deployment_path"),
        ]

        indexes = [
            models.Index(fields=["deployment", "timestamp"]),
            models.Index(fields=["event", "timestamp"]),
            models.Index(fields=["timestamp"]),
        ]


def update_detection_counts(qs: models.QuerySet[SourceImage] | None = None) -> int:
    """
    Update the detection count for all source images using a bulk update query.

    @TODO Needs testing.
    """
    qs = qs or SourceImage.objects.all()
    subquery = models.Subquery(
        Detection.objects.filter(source_image_id=models.OuterRef("pk"))
        .values("source_image_id")
        .annotate(count=models.Count("id"))
        .values("count")
    )
    start_time = time.time()
    num_updated = qs.annotate(count=subquery).update(detections_count=models.F("count"))
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(f"Updated detection counts for {num_updated} source images in {elapsed_time:.2f} seconds")
    return num_updated


def set_dimensions_for_collection(
    event: Event, replace_existing: bool = False, width: int | None = None, height: int | None = None
):
    """
    Set the width & height of all of the images in the event based on one image.

    This will look for the first image in the event that already has dimensions.
    If no images have dimensions, the first image be retrieved from the data source.

    This is much more practical than fetching each image. However if a deployment
    does ever have images with mixed dimensions, another method will be needed.

    @TODO consider adding "assumed image dimensions" to the Deployment instance itself.
    """

    if not width or not height:
        # Try retrieving dimensions from deployment
        width, height = getattr(event.deployment, "assumed_image_dimensions", (None, None))

    if not width or not height:
        # Try retrieving dimensions from the first image that has them already
        image = event.captures.exclude(width__isnull=True, height__isnull=True).first()
        if image:
            width, height = image.width, image.height

    if not width or not height:
        image = event.captures.first()
        if image:
            width, height = image.get_dimensions()

    if width and height:
        logger.info(
            f"Setting dimensions for {event.captures.count()} images in event {event.pk} to " f"{width}x{height}"
        )
        if replace_existing:
            captures = event.captures.all()
        else:
            captures = event.captures.filter(width__isnull=True, height__isnull=True)
        captures.update(width=width, height=height)

    else:
        logger.warning(
            f"Could not determine image dimensions for event {event.pk}. "
            f"Width & height will not be set on any source images."
        )


def sample_captures_by_interval(
    minute_interval: int = 10, qs: models.QuerySet[SourceImage] | None = None, max_num: int | None = None
) -> typing.Generator[SourceImage, None, None]:
    """
    Return a sample of captures from the deployment, evenly spaced apart by minute_interval.
    """

    last_capture = None
    total = 0

    if not qs:
        qs = SourceImage.objects.all()
    qs = qs.exclude(timestamp=None).order_by("timestamp")

    for capture in qs.all():
        if max_num and total >= max_num:
            break
        if not last_capture:
            total += 1
            yield capture
            last_capture = capture
        else:
            assert capture.timestamp and last_capture.timestamp
            delta: datetime.timedelta = capture.timestamp - last_capture.timestamp
            if delta.total_seconds() >= minute_interval * 60:
                total += 1
                yield capture
                last_capture = capture


def sample_captures_by_position(
    position: int,
    qs: models.QuerySet[SourceImage] | None = None,
) -> typing.Generator[SourceImage | None, None, None]:
    """
    Return the n-th position capture from each event.

    For example if position = 0, the first capture from each event will be returned.
    If position = -1, the last capture from each event will be returned.
    """

    if not qs:
        qs = SourceImage.objects.all()
    qs = qs.exclude(timestamp=None).order_by("timestamp")

    events = Event.objects.filter(captures__in=qs).distinct()
    for event in events:
        qs = qs.filter(event=event)
        if position < 0:
            # Negative positions are relative to the end of the queryset
            # e.g. -1 is the last item, -2 is the second last item, etc.
            # but querysets do not support negative indexing, so we
            # sort the queryset in reverse order and then use positive indexing.
            # e.g. -1 becomes 0, -2 becomes 1, etc.
            position = abs(position) - 1
            qs = qs.order_by("-timestamp")
        else:
            qs = qs.order_by("timestamp")
        try:
            capture = qs[position]
        except IndexError:
            # If the position is out of range, just return the last capture
            capture = qs.last()

        yield capture


def sample_captures_by_nth(
    nth: int,
    qs: models.QuerySet[SourceImage] | None = None,
) -> typing.Generator[SourceImage, None, None]:
    """
    Return every nth capture from each event.

    For example if nth = 1, every capture from each event will be returned.
    If nth = 5, every 5th capture from each event will be returned.
    """

    if not qs:
        qs = SourceImage.objects.all()
    qs = qs.exclude(timestamp=None).order_by("timestamp")

    events = Event.objects.filter(captures__in=qs).distinct()
    for event in events:
        qs = qs.filter(event=event).order_by("timestamp")
        yield from qs[::nth]


# @final
# class IdentificationHistory(BaseModel):
#     """A history of identifications for an occurrence."""
#
#     # @TODO
#     pass


@functools.cache
def user_agrees_with_identification(user: "User", occurrence: "Occurrence", taxon: "Taxon") -> bool | None:
    """
    Determine if a user has made an identification of an occurrence that agrees with the given taxon.

    If a user has identified the same occurrence with the same taxon, then they "agree".

    @TODO if we want to reduce this to one query per request, we can accept just User & Occurrence
    then return the list of Taxon IDs that the user has added to that occurrence.
    then the view functions can check if the given taxon is in that list. Or check the list of identifications
    already retrieved by the view.
    """

    # Anonymous users don't have a primary key and will throw an error when used in a query.
    if not user or not user.pk or not taxon or not occurrence:
        return None

    return Identification.objects.filter(
        occurrence=occurrence,
        user=user,
        taxon=taxon,
        withdrawn=False,
    ).exists()


@final
class Identification(BaseModel):
    """A classification of an occurrence by a human."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="identifications",
    )
    taxon = models.ForeignKey(
        "Taxon",
        on_delete=models.SET_NULL,
        null=True,
        related_name="identifications",
    )
    occurrence = models.ForeignKey(
        "Occurrence",
        on_delete=models.CASCADE,
        related_name="identifications",
    )
    withdrawn = models.BooleanField(default=False)
    agreed_with_identification = models.ForeignKey(
        "Identification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agreed_identifications",
    )
    agreed_with_prediction = models.ForeignKey(
        "Classification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agreed_identifications",
    )
    score = 1.0  # Always 1 for humans, at this time
    comment = models.TextField(blank=True)

    class Meta:
        ordering = [
            "-created_at",
        ]

    def save(self, *args, **kwargs):
        """
        If this is a new identification:
        - Set previous identifications by this user to withdrawn
        - Set the determination of the occurrence to the taxon of this identification if it is primary

        # @TODO Add tests
        """

        if not self.pk and not self.withdrawn and self.user:
            # This is a new identification and it has not been explicitly withdrawn
            # so set all other identifications of this user to withdrawn.
            Identification.objects.filter(
                occurrence=self.occurrence,
                user=self.user,
            ).exclude(
                pk=self.pk
            ).update(withdrawn=True)

        super().save(*args, **kwargs)

        update_occurrence_determination(self.occurrence)

    def delete(self, *args, **kwargs):
        """
        If this is the current identification for the occurrence, set the determination to the next best ID.
        and un-withdraw the previous ID by the same user.

        @TODO Add tests
        """
        current_best: Identification | None = self.occurrence.best_identification
        if current_best and current_best == self:
            # Invalidate the cached property so it will be re-calculated
            del self.occurrence.best_identification
            if self.user:
                previous_id = (
                    Identification.objects.filter(
                        occurrence=self.occurrence,
                        user=self.user,
                        withdrawn=True,
                    )
                    .exclude(pk=self.pk)
                    # The "next best" ID by the same user is just the most recent one.
                    # but this could be more complex in the future.
                    .order_by("-created_at")
                    .first()
                )
                if previous_id:
                    previous_id.withdrawn = False
                    previous_id.save()

        super().delete(*args, **kwargs)

        # Allow the update_occurrence_determination to determine the next best ID
        update_occurrence_determination(self.occurrence, current_determination=self.taxon)


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

    # occurrence = models.ForeignKey(
    #     "Occurrence",
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     related_name="predictions",
    # )

    taxon = models.ForeignKey("Taxon", on_delete=models.SET_NULL, null=True, related_name="classifications")
    score = models.FloatField(null=True)
    timestamp = models.DateTimeField()
    # terminal = models.BooleanField(
    #     default=True, help_text="Is this the final classification from a series of classifiers in a pipeline?"
    # )

    softmax_output = models.JSONField(null=True)  # scores for all classes
    raw_output = models.JSONField(null=True)  # raw output from the model

    algorithm = models.ForeignKey(
        "ml.Algorithm",
        on_delete=models.SET_NULL,
        null=True,
    )
    # job = models.CharField(max_length=255, null=True)

    # Type hints for auto-generated fields
    taxon_id: int
    algorithm_id: int

    class Meta:
        ordering = ["-created_at", "-score"]

    def __str__(self) -> str:
        return f"#{self.pk} to Taxon #{self.taxon_id} ({self.score:.2f}) by Algorithm #{self.algorithm_id}"


@final
class Detection(BaseModel):
    """An object detected in an image"""

    source_image = models.ForeignKey(
        SourceImage,
        on_delete=models.CASCADE,
        related_name="detections",
    )

    # @TODO use structured data for bbox
    bbox = models.JSONField(null=True, blank=True)

    # @TODO shouldn't this be automatically set by the source image?
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
        "ml.Algorithm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    # Time that the detection was created by the algorithm in the ML backend
    detection_time = models.DateTimeField(null=True, blank=True)
    # @TODO not sure if this detection score is ever used
    # I think it was intended to be the score of the detection algorithm (bbox score)
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
        # @TODO where is this used?
        classification = (
            self.classifications.order_by("-score")
            .select_related("determination", "determination__name", "score")
            .first()
        )
        if classification and classification.taxon:
            return (str(classification.taxon), classification.score)
        else:
            return (None, None)

    def url(self) -> str | None:
        return get_media_url(self.path) if self.path else None

    def associate_new_occurrence(self) -> "Occurrence":
        """
        Create and associate a new occurrence with this detection.
        """
        if self.occurrence:
            return self.occurrence

        occurrence = Occurrence.objects.create(
            event=self.source_image.event,
            deployment=self.source_image.deployment,
            project=self.source_image.project,
        )
        self.occurrence = occurrence
        self.save()
        occurrence.save()  # Need to save again to update the aggregate values
        # Update aggregate values on source image
        # @TODO this should be done async in a task with an eta of a few seconds
        # so it isn't done for every detection in a batch
        self.source_image.save()
        return occurrence

    def update_calculated_fields(self, save=True):
        needs_update = False
        if not self.timestamp:
            self.timestamp = self.source_image.timestamp
            needs_update = True
        if save and needs_update:
            self.save(update_calculated_fields=False)

    def save(self, update_calculated_fields=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.pk and update_calculated_fields:
            self.update_calculated_fields(save=True)
        # if not self.occurrence:
        #     self.associate_new_occurrence()

    def __str__(self) -> str:
        return f"#{self.pk} from SourceImage #{self.source_image_id} with Algorithm #{self.detection_algorithm_id}"


@final
class OccurrenceManager(models.Manager):
    def get_queryset(self):
        # prefetch determination, deployment, project
        return super().get_queryset().select_related("determination", "deployment", "project")


@final
class Occurrence(BaseModel):
    """An occurrence of a taxon, a sequence of one or more detections"""

    # @TODO change Determination to a nested field with a Taxon, User, Identification, etc like the serializer
    # this could be a OneToOneField to a Determination model or a JSONField validated by a Pydantic model
    determination = models.ForeignKey("Taxon", on_delete=models.SET_NULL, null=True, related_name="occurrences")
    determination_score = models.FloatField(null=True, blank=True)
    # best_detection / determination_detection
    # best_detection_pixel_area

    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, related_name="occurrences")
    deployment = models.ForeignKey(Deployment, on_delete=models.SET_NULL, null=True, related_name="occurrences")
    project = models.ForeignKey("Project", on_delete=models.SET_NULL, null=True, related_name="occurrences")

    detections: models.QuerySet[Detection]
    identifications: models.QuerySet[Identification]

    objects = OccurrenceManager()

    def __str__(self) -> str:
        name = f"Occurrence #{self.pk}"
        if self.deployment:
            name += f" ({self.deployment.name})"
        if self.determination:
            name += f" ({self.determination.name})"
        return name

    def detections_count(self) -> int | None:
        # Annotations don't seem to work with nested serializers
        return self.detections.count()

    @functools.cached_property
    def first_appearance(self) -> SourceImage | None:
        # @TODO it appears we only need the first timestamp, that could be an annotated value
        first = self.detections.order_by("timestamp").select_related("source_image").first()
        if first:
            return first.source_image

    @functools.cached_property
    def last_appearance(self) -> SourceImage | None:
        # @TODO it appears we only need the last timestamp, that could be an annotated value
        last = self.detections.order_by("timestamp").select_related("source_image").last()
        if last:
            return last.source_image

    def first_appearance_timestamp(self) -> datetime.datetime | None:
        """
        Return the timestamp of the first appearance.
        ONLY if it has been added with a query annotation.
        """
        return None

    def first_appearance_time(self) -> datetime.time | None:
        """
        Return the time part only of the first appearance.
        ONLY if it has been added with a query annotation.
        """
        return None

    def last_appearance_timestamp(self) -> datetime.datetime | None:
        """
        Return the timestamp of the last appearance.
        ONLY if it has been added with a query annotation.
        """
        return None

    def duration(self) -> datetime.timedelta | None:
        first = self.first_appearance
        last = self.last_appearance
        if first and last and first.timestamp and last.timestamp:
            return last.timestamp - first.timestamp
        else:
            return None

    def duration_label(self) -> str | None:
        """
        If duration has been calculated by a query annotation, use that value
        otherwise call the duration() method to calculate it.
        """
        duration = self.duration() if callable(self.duration) else self.duration
        return ami.utils.dates.format_timedelta(duration)

    def detection_images(self, limit=None):
        for url in Detection.objects.filter(occurrence=self).values_list("path", flat=True)[:limit]:
            yield urllib.parse.urljoin(_CROPS_URL_BASE, url)

    def pixel_area(self) -> float:
        return 0

    @functools.cached_property
    def best_detection(self):
        return Detection.objects.filter(occurrence=self).order_by("-classifications__score").first()

    @functools.cached_property
    def best_prediction(self):
        return self.predictions().first()

    @functools.cached_property
    def best_identification(self):
        return Identification.objects.filter(occurrence=self, withdrawn=False).order_by("-created_at").first()

    def get_determination_score(self) -> float | None:
        if not self.determination:
            return None
        elif self.best_identification:
            return self.best_identification.score
        elif self.best_prediction:
            return self.best_prediction.score
        else:
            return None

    def predictions(self):
        # Retrieve the classification with the max score for each algorithm
        classifications = (
            Classification.objects.filter(detection__occurrence=self)
            .filter(
                score__in=models.Subquery(
                    Classification.objects.filter(detection__occurrence=self)
                    .values("algorithm")
                    .annotate(max_score=models.Max("score"))
                    .values("max_score")
                )
            )
            .order_by("-created_at")
        )
        return classifications

    def context_url(self):
        detection = self.best_detection
        if detection and detection.source_image and detection.source_image.event:
            # @TODO this was a temporary hack. Use settings and reverse().
            return f"https://app.preview.insectai.org/sessions/{detection.source_image.event.pk}?capture={detection.source_image.pk}&occurrence={self.pk}"  # noqa E501
        else:
            return None

    def url(self):
        # @TODO this was a temporary hack. Use settings and reverse().
        return f"https://app.preview.insectai.org/occurrences/{self.pk}"

    def save(self, update_determination=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if update_determination:
            update_occurrence_determination(
                self,
                current_determination=self.determination,
                save=True,
            )

        if self.determination and not self.determination_score:
            # This may happen for legacy occurrences that were created
            # before the determination_score field was added
            self.determination_score = self.get_determination_score()
            if not self.determination_score:
                logger.warning(f"Could not determine score for {self}")
            else:
                self.save(update_determination=False)

    class Meta:
        ordering = ["-determination_score"]


def update_occurrence_determination(
    occurrence: Occurrence, current_determination: typing.Optional["Taxon"] = None, save=True
):
    """
    Update the determination of the occurrence based on the identifications & predictions.

    If there are identifications, set the determination to the latest identification.
    If there are no identifications, set the determination to the top prediction.

    The `current_determination` is the determination curently saved in the database.
    The `occurrence` object may already have a different un-saved determination set
    so it is neccessary to retrieve the current determination from the database, but
    this can also be passed in as an argument to avoid an extra database query.

    @TODO Add tests for this important method!
    """
    needs_update = False

    # Invalidate the cached properties so they will be re-calculated
    if hasattr(occurrence, "best_identification"):
        del occurrence.best_identification
    if hasattr(occurrence, "best_prediction"):
        del occurrence.best_prediction

    current_determination = (
        current_determination
        or Occurrence.objects.select_related("determination")
        .values("determination")
        .get(pk=occurrence.pk)["determination"]
    )
    new_determination = None
    new_score = None

    top_identification = occurrence.best_identification
    if top_identification and top_identification.taxon and top_identification.taxon != current_determination:
        new_determination = top_identification.taxon
        new_score = top_identification.score
    elif not top_identification:
        top_prediction = occurrence.best_prediction
        if top_prediction and top_prediction.taxon and top_prediction.taxon != current_determination:
            new_determination = top_prediction.taxon
            new_score = top_prediction.score

    if new_determination and new_determination != current_determination:
        logger.info(f"Changing det. of {occurrence} from {current_determination} to {new_determination}")
        occurrence.determination = new_determination
        needs_update = True

    if new_score and new_score != occurrence.determination_score:
        logger.info(f"Changing det. score of {occurrence} from {occurrence.determination_score} to {new_score}")
        occurrence.determination_score = new_score
        needs_update = True

    if save and needs_update:
        occurrence.save(update_determination=False)


@final
class TaxaManager(models.Manager):
    def get_queryset(self):
        # Prefetch parent and parents
        # return super().get_queryset().select_related("parent").prefetch_related("parents")
        return super().get_queryset().select_related("parent")

    def add_genus_parents(self):
        """Add direct genus parents to all species that don't have them, based on the scientific name.

        Create a genus if it doesn't exist based on the scientific name of the species.
        This will replace any parents of a species that are not of the GENUS rank.
        """
        species = self.get_queryset().filter(rank="SPECIES")  # , parent=None)
        updated = []
        for taxon in species:
            if taxon.parent and taxon.parent.rank == "GENUS":
                continue
            genus_name = taxon.name.split()[0]
            genus = self.get_queryset().filter(name=genus_name, rank="GENUS").first()
            if not genus:
                Taxon = self.model
                genus = Taxon.objects.create(name=genus_name, rank="GENUS")
            taxon.parent = genus
            logger.info(f"Added parent {genus} to {taxon}")
            taxon.save()
            updated.append(taxon)
        return updated

    def update_display_names(self, queryset: models.QuerySet | None = None):
        """Update the display names of all taxa."""

        taxa = []

        for taxon in queryset or self.get_queryset():
            taxon.display_name = taxon.get_display_name()
            taxa.append(taxon)

        self.bulk_update(taxa, ["display_name"])

    # Method that returns taxa nested in a tree structure
    def tree(self, root: typing.Optional["Taxon"] = None, filter_ranks: list[TaxonRank] = []) -> dict:
        """Build a recursive tree of taxa."""

        root = root or self.root()

        # Fetch all taxa
        taxa = self.get_queryset().filter(active=True)

        # Build index of taxa by parent
        taxa_by_parent = collections.defaultdict(list)
        for taxon in taxa:
            # Skip adding this taxon if its rank is excluded
            if filter_ranks and TaxonRank(taxon.rank) not in filter_ranks:
                continue

            parent = taxon.parent or root

            # Attach taxa to the nearest parent with a rank that is not excluded
            if filter_ranks and TaxonRank(parent.rank) not in filter_ranks:
                while parent and TaxonRank(parent.rank) not in filter_ranks:
                    parent = parent.parent

            if parent != taxon:
                taxa_by_parent[parent].append(taxon)

        # Recursively build a nested tree
        def _tree(taxon):
            return {
                "taxon": taxon,
                "children": [_tree(child) for child in taxa_by_parent[taxon]],
            }

        if filter_ranks and TaxonRank(root.rank) not in filter_ranks:
            raise ValueError(f"Cannot filter rank {root.rank} from tree because the root taxon must be included")

        return _tree(root)

    def tree_of_names(self, root: typing.Optional["Taxon"] = None) -> dict:
        """
        Build a recursive tree of taxon names.

        Names in the database are not not formatted as nicely as the python-rendered versions.
        """

        root = root or self.root()

        # Fetch all names and parent names
        names = self.get_queryset().filter(active=True).values_list("name", "parent__name")

        # Index names by parent name
        names_by_parent = collections.defaultdict(list)
        for name, parent_name in names:
            names_by_parent[parent_name].append(name)

        # Recursively build a nested tree

        def _tree(name):
            return {
                "name": name,
                "children": [_tree(child) for child in names_by_parent[name]],
            }

        return _tree(root.name)

    def root(self):
        """Get the root taxon, the one with no parent and the highest taxon rank."""

        for rank in list(TaxonRank):
            taxon = self.get_queryset().filter(parent=None, rank=rank.name).first()
            if taxon:
                return taxon

        root = self.get_queryset().filter(parent=None).first()
        assert root, "No root taxon found"
        return root


@final
class Taxon(BaseModel):
    """A taxonomic classification"""

    name = models.CharField(max_length=255, unique=True)
    display_name = models.CharField("Cached display name", max_length=255, null=True, blank=True, unique=True)
    rank = models.CharField(max_length=255, choices=TaxonRank.choices(), default=TaxonRank.SPECIES.name)
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="direct_children"
    )
    # @TODO this parents field could be replaced by a cached JSON field with the proper ordering of ranks
    parents = models.ManyToManyField("self", related_name="children", symmetrical=False, blank=True)
    # taxonomy = models.JSONField(null=True, blank=True)
    active = models.BooleanField(default=True)
    synonym_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="synonyms")

    gbif_taxon_key = models.BigIntegerField("GBIF taxon key", blank=True, null=True)
    bold_taxon_bin = models.CharField("BOLD taxon BIN", max_length=255, blank=True, null=True)
    inat_taxon_id = models.BigIntegerField("iNaturalist taxon ID", blank=True, null=True)

    notes = models.TextField(blank=True)

    projects = models.ManyToManyField("Project", related_name="taxa")
    direct_children: models.QuerySet["Taxon"]
    children: models.QuerySet["Taxon"]
    occurrences: models.QuerySet[Occurrence]
    classifications: models.QuerySet["Classification"]
    lists: models.QuerySet["TaxaList"]

    author = models.CharField(max_length=255, blank=True)
    authorship_date = models.DateField(null=True, blank=True, help_text="The date the taxon was described.")
    ordering = models.IntegerField(null=True, blank=True)
    sort_phylogeny = models.BigIntegerField(blank=True, null=True)

    objects: TaxaManager = TaxaManager()

    def __str__(self) -> str:
        name_with_rank = f"{self.name} ({self.rank})"
        return name_with_rank

    def get_display_name(self):
        """
        This must be unique because it is used for choice keys in Label Studio.
        """
        if self.rank == "SPECIES":
            return self.name
        elif self.rank == "GENUS":
            return f"{self.name} sp."
        # elif self.rank not in ["ORDER", "FAMILY"]:
        #     return f"{self.name} ({self.rank})"
        else:
            return self.name

    def get_rank(self) -> TaxonRank:
        """
        Return the rank str value as a TaxonRank enum.
        """
        return TaxonRank(self.rank)

    def num_direct_children(self) -> int:
        return self.direct_children.count()

    def num_children_recursive(self) -> int:
        # @TODO how to do this with a single query?
        return self.children.count() + sum(child.num_children_recursive() for child in self.children.all())

    def occurrences_count(self) -> int:
        # return self.occurrences.count()
        return 0

    def detections_count(self) -> int:
        # return Detection.objects.filter(occurrence__determination=self).count()
        return 0

    def events_count(self) -> int:
        return 0

    def latest_occurrence(self) -> Occurrence | None:
        return self.occurrences.order_by("-created_at").first()

    def latest_detection(self) -> Detection | None:
        return Detection.objects.filter(occurrence__determination=self).order_by("-created_at").first()

    def last_detected(self) -> datetime.datetime | None:
        # This is handled by an annotation
        return None

    def best_determination_score(self) -> float | None:
        # This is handled by an annotation if we are filtering by project, deployment or event
        return None

    def occurrence_images(
        self,
        limit: int | None = 10,
        project_id: int | None = None,
        classification_threshold: float | None = None,
    ) -> list[str]:
        """
        Return one image from each occurrence of this Taxon.
        The image should be from the detection with the highest classification score.

        This is used for image thumbnail previews in the species summary view.

        The project ID is an optional filter however
        @TODO important, this should always filter by what the current user has access to.
        Use the request.user to filter by the user's access.
        Use the request to generate the full media URLs.
        """

        classification_threshold = classification_threshold or settings.DEFAULT_CONFIDENCE_THRESHOLD

        # Retrieve the URLs using a single optimized query
        qs = (
            self.occurrences.prefetch_related(
                models.Prefetch(
                    "detections__classifications",
                    queryset=Classification.objects.filter(score__gte=classification_threshold).order_by("-score"),
                )
            )
            .annotate(max_score=models.Max("detections__classifications__score"))
            .filter(detections__classifications__score=models.F("max_score"))
            .order_by("-max_score")
        )
        if project_id is not None:
            # @TODO this should check the user's access instead
            qs = qs.filter(project=project_id)

        detection_image_paths = qs.values_list("detections__path", flat=True)[:limit]

        # @TODO should this be done in the serializer?
        # @TODO better way to get distinct values from an annotated queryset?
        return [get_media_url(path) for path in detection_image_paths if path]

    def list_names(self) -> str:
        return ", ".join(self.lists.values_list("name", flat=True))

    def update_parents(self, save=True):
        """
        Populate the cached "parents" list by recursively following the "parent" field.

        @TODO this requires the parents' parents already being up-to-date, which may not always be the case.
        @TODO parents could instead be a JSON field that is updated by a trigger on the database.
        """

        taxon = self
        parents = [taxon.parent]
        while parents[-1] is not None:
            parents.append(parents[-1].parent)
        parents = parents[:-1]
        taxon.parents.set(parents)
        if save:
            taxon.save()

    class Meta:
        ordering = [
            "ordering",
            "name",
        ]
        verbose_name_plural = "Taxa"

        # Set unique constraints on name & rank
        # constraints = [
        #     models.UniqueConstraint(fields=["name", "rank", "parent"], name="unique_name_and_placement"),
        # ]
        indexes = [
            # Add index for default ordering
            models.Index(fields=["ordering", "name"]),
        ]

    def save(self, *args, **kwargs):
        """Update the display name before saving."""
        self.display_name = self.get_display_name()
        super().save(*args, **kwargs)


@final
class TaxaList(BaseModel):
    """A checklist of taxa"""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    taxa = models.ManyToManyField(Taxon, related_name="lists")
    projects = models.ManyToManyField("Project", related_name="taxa_lists")

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Taxa Lists"


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


@final
class Page(BaseModel):
    """Barebones page model for static pages like About & Contact."""

    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=255, unique=True, help_text="Unique, URL safe name e.g. about-us")
    content = models.TextField("Body content", blank=True, null=True, help_text="Use Markdown syntax")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="pages", null=True, blank=True)
    link_class = models.CharField(max_length=255, blank=True, null=True, help_text="CSS class for nav link")
    nav_level = models.IntegerField(default=0, help_text="0 = main nav, 1 = sub nav, etc.")
    nav_order = models.IntegerField(default=0, help_text="Order of nav items within a level")
    published = models.BooleanField(default=False)

    class Meta:
        ordering = ["nav_level", "nav_order", "name"]

    def __str__(self) -> str:
        return self.name

    def html(self) -> str:
        """Convert the content field to HTML"""
        from markdown import markdown

        if self.content:
            return markdown(self.content, extensions=[])
        else:
            return ""


_SOURCE_IMAGE_SAMPLING_METHODS = [
    "common_combined",
    "random",
    "stratified_random",
    "interval",
    "manual",
    "starred",
    "random_from_each_event",
    "last_and_random_from_each_event",
    "greatest_file_size_from_each_event",
    "detections_only",
]


@final
class SourceImageCollection(BaseModel):
    """
    A subset of source images for review, processing, etc.

    Examples:
        - Random subset
        - Stratified random sample from all deployments
        - Images sampled based on a time interval (every 30 minutes)


    Collections are saved so that they can be reviewed or re-used later.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    images = models.ManyToManyField("SourceImage", related_name="collections", blank=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="sourceimage_collections")
    method = models.CharField(
        max_length=255,
        choices=as_choices(_SOURCE_IMAGE_SAMPLING_METHODS),
        default="common_combined",
    )
    # @TODO this should be a JSON field with a schema, use a pydantic model
    kwargs = models.JSONField(
        "Arguments",
        null=True,
        blank=True,
        help_text="Arguments passed to the sampling function (JSON dict)",
        default=dict,
    )

    def source_image_count(self) -> int:
        # This should always be pre-populated using queryset annotations
        return self.images.count()

    def get_queryset(self):
        return SourceImage.objects.filter(project=self.project)

    @classmethod
    def sampling_methods(cls):
        return [method for method in dir(cls) if method.startswith("sample_")]

    def populate_sample(self):
        """Create a sample of source images based on the method and kwargs"""
        kwargs = self.kwargs or {}

        method_name = f"sample_{self.method}"
        if not hasattr(self, method_name):
            raise ValueError(f"Invalid sampling method: {self.method}. Choices are: {_SOURCE_IMAGE_SAMPLING_METHODS}")
        else:
            method = getattr(self, method_name)
            self.images.set(method(**kwargs))
            self.save()

    def sample_random(self, size: int = 100):
        """Create a random sample of source images"""

        qs = self.get_queryset()
        return qs.order_by("?")[:size]

    def sample_manual(self, image_ids: list[int]):
        """Create a sample of source images based on a list of source image IDs"""

        qs = self.get_queryset()
        return qs.filter(id__in=image_ids)

    def sample_common_combined(
        self,
        minute_interval: int | None = None,
        max_num: int | None = 100,
        hour_start: int | None = None,
        hour_end: int | None = None,
        month_start: datetime.date | None = None,
        month_end: datetime.date | None = None,
    ) -> list[SourceImage]:
        qs = self.get_queryset()
        if month_start:
            qs = qs.filter(timestamp__month__gte=month_start)
        if month_end:
            qs = qs.filter(timestamp__month__lte=month_end)
        if hour_start:
            qs = qs.filter(timestamp__hour__gte=hour_start)
        if hour_end:
            qs = qs.filter(timestamp__hour__lte=hour_end)
        if minute_interval:
            # @TODO can this be done in the database and return a queryset?
            # this currently returns a list of source images
            qs = list(sample_captures_by_interval(minute_interval, qs, max_num=max_num))
        if max_num:
            qs = qs[:max_num]
        captures = list(qs)
        return captures

    def sample_interval(
        self, minute_interval: int = 10, exclude_events: list[int] = [], deployment_id: int | None = None
    ):
        """Create a sample of source images based on a time interval"""

        qs = self.get_queryset()
        if deployment_id:
            qs = qs.filter(deployment=deployment_id)
        if exclude_events:
            qs = qs.exclude(event__in=exclude_events)
        qs.exclude(event__in=exclude_events)
        return sample_captures_by_interval(minute_interval, qs)

    def sample_positional(self, position: int = -1):
        """Sample the single nth source image from all events in the project"""

        qs = self.get_queryset()
        return sample_captures_by_position(position, qs)

    def sample_nth(self, nth: int):
        """Sample every nth source image from all events in the project"""

        qs = self.get_queryset()
        return sample_captures_by_nth(nth, qs)

    def sample_random_from_each_event(self, num_each: int = 10):
        """Sample n random source images from each event in the project."""

        qs = self.get_queryset()
        captures = set()
        for event in self.project.events.all():
            captures.update(qs.filter(event=event).order_by("?")[:num_each])
        return captures

    def sample_last_and_random_from_each_event(self, num_each: int = 1):
        """Sample the last image from each event and n random from each event."""

        qs = self.get_queryset()
        captures = set()
        for event in self.project.events.all():
            last_capture = qs.filter(event=event).order_by("timestamp").last()
            if not last_capture:
                # This event has no captures
                continue
            captures.add(last_capture)
            random_captures = qs.filter(event=event).exclude(pk=last_capture.pk).order_by("?")[:num_each]
            captures.update(random_captures)
        return captures

    def sample_greatest_file_size_from_each_event(self, num_each: int = 1):
        """Sample the image with the greatest file size from each event."""

        qs = self.get_queryset()
        captures = set()
        for event in self.project.events.all():
            captures.update(qs.filter(event=event).order_by("-size")[:num_each])
        return captures

    def sample_detections_only(self):
        """Sample all source images with detections"""

        qs = self.get_queryset()
        return qs.filter(detections__isnull=False).distinct()

    @classmethod
    def get_or_create_starred_collection(cls, project: Project) -> "SourceImageCollection":
        """
        Get or create a collection for starred images.
        """
        collection = (
            SourceImageCollection.objects.filter(
                project=project,
                method="starred",
            )
            .order_by("created_at")
            .first()
        )  # Use the oldest match
        if not collection:
            collection = SourceImageCollection.objects.create(
                project=project,
                method="starred",
                name="Starred Images",  # @TODO make this translatable
            )
        return collection
