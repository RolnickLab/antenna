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

import pydantic
from django.apps import apps
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import IntegrityError, models
from django.db.models import Q
from django.db.models.fields.files import ImageFieldFile
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.template.defaultfilters import filesizeformat
from django.utils import timezone
from django_pydantic_field import SchemaField

import ami.tasks
import ami.utils
from ami.base.fields import DateStringField
from ami.base.models import BaseModel
from ami.main import charts
from ami.users.models import User
from ami.utils.schemas import OrderedEnum

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job

logger = logging.getLogger(__name__)

# Constants
_POST_TITLE_MAX_LENGTH: Final = 80


class TaxonRank(OrderedEnum):
    KINGDOM = "KINGDOM"
    PHYLUM = "PHYLUM"
    CLASS = "CLASS"
    ORDER = "ORDER"
    SUPERFAMILY = "SUPERFAMILY"
    FAMILY = "FAMILY"
    SUBFAMILY = "SUBFAMILY"
    TRIBE = "TRIBE"
    SUBTRIBE = "SUBTRIBE"
    GENUS = "GENUS"
    SPECIES = "SPECIES"
    UNKNOWN = "UNKNOWN"


DEFAULT_RANKS = sorted(
    [
        TaxonRank.KINGDOM,
        TaxonRank.PHYLUM,
        TaxonRank.CLASS,
        TaxonRank.ORDER,
        TaxonRank.FAMILY,
        TaxonRank.SUBFAMILY,
        TaxonRank.TRIBE,
        TaxonRank.GENUS,
        TaxonRank.SPECIES,
    ]
)


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
        # @TODO add a file field to the Detection model and use that to get the URL
        url = default_storage.url(path.lstrip("/"))
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


class ProjectQuerySet(models.QuerySet):
    def filter_by_user(self, user: User):
        """
        Filters projects to include only those where the given user is a member.
        """
        return self.filter(members=user)


class ProjectManager(models.Manager):
    def get_queryset(self) -> ProjectQuerySet:
        return ProjectQuerySet(self.model, using=self._db)


@final
class Project(BaseModel):
    """ """

    name = models.CharField(max_length=_POST_TITLE_MAX_LENGTH)
    description = models.TextField()
    image = models.ImageField(upload_to="projects", blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="projects")
    members = models.ManyToManyField(User, related_name="user_projects", blank=True)
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
    jobs: models.QuerySet["Job"]
    objects = ProjectManager()

    def get_project(self):
        return self

    def ensure_owner_membership(self):
        """Add owner to members if they are not already a member"""
        if self.owner and not self.members.filter(id=self.owner.pk).exists():
            self.members.add(self.owner)

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
            # plots.append(charts.occurrences_accumulated(project_pk=self.pk))
        else:
            plots.append(charts.events_per_month(project_pk=self.pk))
            # plots.append(charts.captures_per_month(project_pk=self.pk))
        plots.append(charts.project_top_taxa(project_pk=self.pk))
        plots.append(charts.average_occurrences_per_month(project_pk=self.pk))
        plots.append(charts.unique_species_per_month(project_pk=self.pk))

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
        # Add owner to members
        self.ensure_owner_membership()
        if new_project:
            logger.info(f"Created new project {self}")
            self.create_related_defaults()

    class Permissions:
        """CRUD Permission names follow the convention: `create_<model>`, `update_<model>`,
        `delete_<model>`, `view_<model>`"""

        # Project permissions
        VIEW = "view_project"
        CHANGE = "update_project"
        DELETE = "delete_project"
        ADD = "create_project"

        # Identification permissions
        CREATE_IDENTIFICATION = "create_identification"
        UPDATE_IDENTIFICATION = "update_identification"
        DELETE_IDENTIFICATION = "delete_identification"

        # Job permissions
        CREATE_JOB = "create_job"
        UPDATE_JOB = "update_job"
        RUN_JOB = "run_job"
        DELETE_JOB = "delete_job"
        RETRY_JOB = "retry_job"
        CANCEL_JOB = "cancel_job"

        # Deployment permissions
        CREATE_DEPLOYMENT = "create_deployment"
        DELETE_DEPLOYMENT = "delete_deployment"
        UPDATE_DEPLOYMENT = "update_deployment"

        # Collection permissions
        CREATE_COLLECTION = "create_sourceimagecollection"
        UPDATE_COLLECTION = "update_sourceimagecollection"
        DELETE_COLLECTION = "delete_sourceimagecollection"
        POPULATE_COLLECTION = "populate_sourceimagecollection"

        # Source Image permissions
        STAR_SOURCE_IMAGE = "star_sourceimage"

        # Storage permissions
        CREATE_STORAGE = "create_s3storagesource"
        DELETE_STORAGE = "delete_s3storagesource"
        UPDATE_STORAGE = "update_s3storagesource"

        # Site permissions
        CREATE_SITE = "create_site"
        DELETE_SITE = "delete_site"
        UPDATE_SITE = "update_site"

        # Device permissions
        CREATE_DEVICE = "create_device"
        DELETE_DEVICE = "delete_device"
        UPDATE_DEVICE = "update_device"

        # Other permissions
        VIEW_PRIVATE_DATA = "view_private_data"
        TRIGGER_EXPORT = "trigger_export"
        DELETE_OCCURRENCES = "delete_occurrences"
        IMPORT_DATA = "import_data"
        MANAGE_MEMBERS = "manage_members"

    class Meta:
        ordering = ["-priority", "created_at"]
        permissions = [
            # Identification permissions
            ("create_identification", "Can create identifications"),
            ("update_identification", "Can update identifications"),
            ("delete_identification", "Can delete identifications"),
            # Job permissions
            ("create_job", "Can create a job"),
            ("update_job", "Can update a job"),
            ("run_job", "Can run a job"),
            ("delete_job", "Can delete a job"),
            ("retry_job", "Can retry a job"),
            ("cancel_job", "Can cancel a job"),
            # Deployment permissions
            ("create_deployment", "Can create a deployment"),
            ("delete_deployment", "Can delete a deployment"),
            ("update_deployment", "Can update a deployment"),
            # Collection permissions
            ("create_sourceimagecollection", "Can create a collection"),
            ("update_sourceimagecollection", "Can update a collection"),
            ("delete_sourceimagecollection", "Can delete a collection"),
            ("populate_sourceimagecollection", "Can populate a collection"),
            # Source Image permissions
            ("star_sourceimage", "Can star a source image"),
            # Storage permissions
            ("create_s3storagesource", "Can create storage"),
            ("delete_s3storagesource", "Can delete storage"),
            ("update_s3storagesource", "Can update storage"),
            # Site permissions
            ("create_site", "Can create a site"),
            ("delete_site", "Can delete a site"),
            ("update_site", "Can update a site"),
            # Device permissions
            ("create_device", "Can create a device"),
            ("delete_device", "Can delete a device"),
            ("update_device", "Can update a device"),
            # Other permissions
            ("view_private_data", "Can view private data"),
            ("trigger_exports", "Can trigger data exports"),
        ]


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
    # Or a pydantic model with nested attributes about each data source relationship
    data_source = models.ForeignKey(
        "S3StorageSource", on_delete=models.SET_NULL, null=True, blank=True, related_name="deployments"
    )

    # Pre-calculated values from the data source
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

    # Pre-calculated values
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
    jobs: models.QuerySet["Job"]

    objects = DeploymentManager()

    class Meta:
        ordering = ["name"]

    def taxa(self) -> models.QuerySet["Taxon"]:
        return Taxon.objects.filter(Q(occurrences__deployment=self)).distinct()

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

    def data_source_total_size_display(self) -> str:
        if self.data_source_total_size is None:
            return filesizeformat(0)
        else:
            return filesizeformat(self.data_source_total_size)

    def sync_captures(self, batch_size=1000, regroup_events_per_batch=False, job: "Job | None" = None) -> int:
        """Import images from the deployment's data source"""

        deployment = self
        assert deployment.data_source, f"Deployment {deployment.name} has no data source configured"

        s3_config = deployment.data_source.config
        total_size = 0
        total_files = 0
        source_images = []
        django_batch_size = batch_size
        sql_batch_size = 1000

        if job:
            job.logger.info(f"Syncing captures for deployment {deployment}")
            job.update_progress()
            job.save()

        for obj, file_index in ami.utils.s3.list_files_paginated(
            s3_config,
            subdir=self.data_source_subdir,
            regex_filter=self.data_source_regex,
        ):
            logger.debug(f"Processing file {file_index}: {obj}")
            if not obj:
                continue
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
                if job:
                    job.logger.info(f"Processed {total_files} files")
                    job.progress.update_stage(job.job_type().key, total_files=total_files)
                    job.update_progress()

        if source_images:
            # Insert/update the last batch
            _insert_or_update_batch_for_sync(
                deployment, source_images, total_files, total_size, sql_batch_size, regroup_events_per_batch
            )
        if job:
            job.logger.info(f"Processed {total_files} files")
            job.progress.update_stage(job.job_type().key, total_files=total_files)
            job.update_progress()

        _compare_totals_for_sync(deployment, total_files)

        # @TODO decide if we should delete SourceImages that are no longer in the data source

        if job:
            job.logger.info("Saving and recalculating sessions for deployment")
            job.progress.update_stage(job.job_type().key, progress=1)
            job.progress.add_stage("Update deployment cache")
            job.update_progress()

        self.save()
        self.update_calculated_fields(save=True)

        if job:
            job.progress.update_stage("Update deployment cache", progress=1)
            job.update_progress()

        return total_files

    def audit_subdir_of_captures(self, ignore_deepest=False) -> dict[str, int]:
        """
        Review the subdirs of all captures that belong to this deployment in an efficient query.

        Group all captures by their subdir and count the number of captures in each group.
        `ignore_deepest` will exclude the deepest subdir from the audit (usually the date folder)
        """

        class SubdirExtractAll(models.Func):
            function = "REGEXP_REPLACE"
            template = "%(function)s(%(expressions)s, '/[^/]*$', '')"

        class SubdirExtractParent(models.Func):
            # Attempts failed to dynamically set the depth of the last directories to ignore.
            # so this is a hardcoded version that ignores the last one directory.
            # this is useful for ignoring the date folder in the path.
            function = "REGEXP_REPLACE"
            template = "%(function)s(%(expressions)s, '/[^/]*/[^/]*$', '')"

        extract_func = SubdirExtractParent if ignore_deepest else SubdirExtractAll

        subdirs_audit = (
            self.captures.annotate(
                subdir=models.Case(
                    models.When(path__contains="/", then=extract_func(models.F("path"))),
                    default=models.Value(""),
                    output_field=models.CharField(),
                )
            )
            .values("subdir")
            .annotate(count=models.Count("id"))
            .exclude(subdir="")
            .order_by("-count")
        )

        # Convert QuerySet to dictionary
        return {item["subdir"]: item["count"] for item in subdirs_audit}

    def update_subdir_of_captures(self, previous_subdir: str, new_subdir: str):
        """
        Update the relative directory in the path of all captures that belong to this deployment in a single query.

        This is useful when moving images to a new location in the data source. It is not run
        automatically when the deployment's data source configuration is updated. But admins can
        run it manually from the Django shell or a maintenance script.

        Reminder: the public_base_url includes the path that precedes the subdir within the full file path.

        Warning: this is essentially a find & replace operation on the path field of SourceImage objects.
        """

        # Sanitize the subdir strings. Ensure that they end with a slash. This is are only protection against
        # accidentally modifying the filename.
        # Relative paths are stored without a leading slash.
        previous_subdir = previous_subdir.strip("/") + "/"
        new_subdir = new_subdir.strip("/") + "/"

        # Update the path of all captures that belong to this deployment
        captures = SourceImage.objects.filter(deployment=self, path__startswith=previous_subdir)
        logger.info(f"Updating subdir of {captures.count()} captures from '{previous_subdir}' to '{new_subdir}'")
        previous_count = captures.count()
        captures.update(
            path=models.functions.Replace(
                models.F("path"),
                models.Value(previous_subdir),
                models.Value(new_subdir),
            )
        )
        # Re-query the captures to ensure the path has been updated
        unchanged_count = SourceImage.objects.filter(deployment=self, path__startswith=previous_subdir).count()
        changed_count = SourceImage.objects.filter(deployment=self, path__startswith=new_subdir).count()

        if unchanged_count:
            raise ValueError(f"{unchanged_count} captures were not updated to new subdir: {new_subdir}")

        if changed_count != previous_count:
            raise ValueError(f"Only {changed_count} captures were updated to new subdir: {new_subdir}")

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
            qs = model.objects.filter(deployment=self).exclude(project=self.project)
            project_values = set(qs.values_list("project", flat=True).distinct())
            if len(project_values):
                logger.warning(
                    f"Deployment {self} has alternate projects set on {model_name} "
                    f"objects: {project_values}. Updating them!"
                )
            qs.update(project=self.project)

    def update_calculated_fields(self, save=False):
        """Update calculated fields on the deployment."""

        self.data_source_total_files = self.captures.count()
        self.data_source_total_size = self.captures.aggregate(total_size=models.Sum("size")).get("total_size")

        self.events_count = self.events.count()
        self.captures_count = self.data_source_total_files or self.captures.count()
        self.detections_count = Detection.objects.filter(Q(source_image__deployment=self)).count()
        self.occurrences_count = (
            self.occurrences.filter(
                event__isnull=False,
            )
            .distinct()
            .count()
        )
        self.taxa_count = (
            Taxon.objects.filter(
                occurrences__deployment=self,
                occurrences__event__isnull=False,
            )
            .distinct()
            .count()
        )

        self.first_capture_timestamp, self.last_capture_timestamp = self.get_first_and_last_timestamps()

        if save:
            self.save(update_calculated_fields=False)

    def save(self, update_calculated_fields=True, *args, **kwargs):
        if self.pk:
            events_last_updated = min(
                [
                    self.events.aggregate(latest_updated_at=models.Max("updated_at")).get("latest_update_at")
                    or datetime.datetime.max,
                    self.updated_at,
                ]
            )
        else:
            events_last_updated = datetime.datetime.min

        super().save(*args, **kwargs)
        if self.pk and update_calculated_fields:
            # @TODO Use "dirty" flag strategy to only update when needed
            new_or_updated_captures = self.captures.filter(updated_at__gte=events_last_updated).count()
            deleted_captures = True if self.captures.count() < (self.captures_count or 0) else False
            if new_or_updated_captures or deleted_captures:
                ami.tasks.regroup_events.delay(self.pk)
            self.update_calculated_fields(save=True)
            if self.project:
                self.update_children()
                # @TODO this isn't working as a background task
                # ami.tasks.model_task.delay("Project", self.project.pk, "update_children_project")


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

    # Pre-calculated values
    captures_count = models.IntegerField(blank=True, null=True)
    detections_count = models.IntegerField(blank=True, null=True)
    occurrences_count = models.IntegerField(blank=True, null=True)
    calculated_fields_updated_at = models.DateTimeField(blank=True, null=True)

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

    def get_captures_count(self) -> int:
        return self.captures.distinct().count()

    def get_detections_count(self) -> int | None:
        return Detection.objects.filter(Q(source_image__event=self)).count()

    def get_occurrences_count(self, classification_threshold: float = 0) -> int:
        return self.occurrences.distinct().filter(determination_score__gte=classification_threshold).count()

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

    def taxa_count(self, classification_threshold: float = 0) -> int:
        # Move this to a pre-calculated field or prefetch_related in the view
        # return self.taxa(classification_threshold).count()
        return 0

    def taxa(self, classification_threshold: float = 0) -> models.QuerySet["Taxon"]:
        return Taxon.objects.filter(
            Q(occurrences__event=self),
            occurrences__determination_score__gte=classification_threshold,
        ).distinct()

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

    def update_calculated_fields(self, save=False, updated_timestamp: datetime.datetime | None = None):
        """
        Important: if you update a new field, add it to the bulk_update call in update_calculated_fields_for_events
        """
        event = self
        if not event.group_by and event.start:
            # If no group_by is set, use the start "day"
            event.group_by = str(event.start.date())

        if not event.project and event.deployment:
            event.project = event.deployment.project

        if event.pk is not None:
            # Can only update start and end times if this is an update to an existing event
            first = event.captures.order_by("timestamp").values("timestamp").first()
            last = event.captures.order_by("-timestamp").values("timestamp").first()
            if first:
                event.start = first["timestamp"]
            if last:
                event.end = last["timestamp"]

            event.captures_count = event.get_captures_count()
            event.detections_count = event.get_detections_count()
            event.occurrences_count = event.get_occurrences_count()

            event.calculated_fields_updated_at = updated_timestamp or timezone.now()

        if save:
            event.save(update_calculated_fields=False)

    def save(self, update_calculated_fields=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if update_calculated_fields:
            self.update_calculated_fields(save=True)


def update_calculated_fields_for_events(
    qs: models.QuerySet[Event] | None = None,
    pks: list[typing.Any] | None = None,
    last_updated: datetime.datetime | None = None,
    save=True,
):
    """
    This function is called by a migration to update the calculated fields for all events.

    @TODO this can likely be abstracted to a more generic function that can be used for any model
    """
    to_update = []

    qs = qs or Event.objects.all()
    if pks:
        qs = qs.filter(pk__in=pks)
    if last_updated:
        # query for None or before the last updated time
        qs = qs.filter(
            Q(calculated_fields_updated_at__isnull=True) | Q(calculated_fields_updated_at__lte=last_updated)
        )

    logging.info(f"Updating pre-calculated fields for {len(to_update)} events")

    updated_timestamp = timezone.now()
    for event in qs:
        event.update_calculated_fields(save=False, updated_timestamp=updated_timestamp)
        to_update.append(event)

    if save:
        updated_count = Event.objects.bulk_update(
            to_update,
            [
                "group_by",
                "start",
                "end",
                "project",
                "captures_count",
                "detections_count",
                "occurrences_count",
                "calculated_fields_updated_at",
            ],
        )
        if updated_count != len(to_update):
            logging.error(f"Failed to update {len(to_update) - updated_count} events")
    return to_update


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
            f"Found {len(values)} images with the same timestamp in deployment '{deployment}'. "
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

    logger.info(
        f"Done grouping {len(image_timestamps)} captures into {len(events)} events " f"for deployment {deployment}"
    )

    if delete_empty:
        logger.info("Deleting empty events for deployment")
        delete_empty_events(deployment=deployment)

    for event in events:
        # Set the width and height of all images in each event based on the first image
        logger.info(f"Setting image dimensions for event {event}")
        set_dimensions_for_collection(event)

    logger.info("Checking for unusual statistics of events")
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

    logger.info("Updating relevant cached fields on deployment")
    deployment.events_count = len(events)
    deployment.save(update_calculated_fields=False, update_fields=["events_count"])

    return events


def delete_empty_events(deployment: Deployment, dry_run=False):
    """
    Delete events that have no images, occurrences or other related records.
    """

    # @TODO Search all models that have a foreign key to Event
    # related_models = [
    #     f.related_model
    #     for f in Event._meta.get_fields()
    #     if f.one_to_many or f.one_to_one or (f.many_to_many and f.auto_created)
    # ]

    events = (
        Event.objects.filter(deployment=deployment)
        .annotate(
            num_images=models.Count("captures"),
            num_occurrences=models.Count("occurrences"),
        )
        .filter(num_images=0, num_occurrences=0)
    )

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
    public_base_url = models.CharField(max_length=255, blank=True, null=True)
    total_size = models.BigIntegerField(null=True, blank=True)
    total_files = models.BigIntegerField(null=True, blank=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    # last_check_duration = models.DurationField(null=True, blank=True)
    # use_signed_urls = models.BooleanField(default=False)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name="storage_sources")

    deployments: models.QuerySet["Deployment"]

    @property
    def config(self) -> ami.utils.s3.S3Config:
        return ami.utils.s3.S3Config(
            bucket_name=self.bucket,
            prefix=self.prefix,
            access_key_id=self.access_key,
            secret_access_key=self.secret_key,
            endpoint_url=self.endpoint_url,
            public_base_url=self.public_base_url,
        )

    def deployments_count(self) -> int:
        return self.deployments.count()

    def total_files_indexed(self) -> int:
        return self.deployments.aggregate(total_files=models.Sum("data_source_total_files"))["total_files"]

    @functools.cache
    def total_size_indexed(self) -> int:
        return self.deployments.aggregate(total_size=models.Sum("data_source_total_size"))["total_size"]

    def total_size_indexed_display(self) -> str:
        return filesizeformat(self.total_size_indexed())

    def total_captures_indexed(self) -> int:
        return self.deployments.aggregate(total_captures=models.Sum("captures_count"))["total_captures"]

    def list_files(self, limit=None):
        """Recursively list files in the bucket/prefix."""

        return ami.utils.s3.list_files_paginated(self.config, limit=limit)

    def count_files(self):
        """Count & save the number of files in the bucket/prefix."""

        count = ami.utils.s3.count_files_paginated(self.config)
        self.total_files = count
        self.save()
        return count

    def calculate_size(self):
        """Calculate the total size and count of all files in the bucket/prefix."""

        sizes = [obj["Size"] for obj, _num_files_checked in self.list_files() if obj]  # type: ignore
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

    def test_connection(
        self, subdir: str | None = None, regex_filter: str | None = None
    ) -> ami.utils.s3.ConnectionTestResult:
        """Test the connection to the S3 bucket."""

        return ami.utils.s3.test_connection(self.config, subdir=subdir, regex_filter=regex_filter)

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


def create_source_image_from_upload(image: ImageFieldFile, deployment: Deployment, request=None) -> "SourceImage":
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
    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE, related_name="manually_uploaded_captures")
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


class SourceImageQuerySet(models.QuerySet):
    def with_occurrences_count(self, classification_threshold: float = 0):
        return self.annotate(
            occurrences_count=models.Count(
                "detections__occurrence",
                filter=models.Q(
                    detections__occurrence__determination_score__gte=classification_threshold,
                ),
                distinct=True,
            )
        )

    def with_taxa_count(self, classification_threshold: float = 0):
        return self.annotate(
            taxa_count=models.Count(
                "detections__occurrence__determination",
                filter=models.Q(
                    detections__occurrence__determination_score__gte=classification_threshold,
                ),
                distinct=True,
            )
        )


class SourceImageManager(models.Manager):
    def get_queryset(self) -> SourceImageQuerySet:
        return SourceImageQuerySet(self.model, using=self._db)


@final
class SourceImage(BaseModel):
    """A single image captured during a monitoring session"""

    path = models.CharField(max_length=255, blank=True)
    public_base_url = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(null=True, blank=True, db_index=True)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    size = models.BigIntegerField(null=True, blank=True)
    last_modified = models.DateTimeField(null=True, blank=True)
    checksum = models.CharField(max_length=255, blank=True, null=True)
    checksum_algorithm = models.CharField(max_length=255, blank=True, null=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    test_image = models.BooleanField(default=False)

    # Precaclulated values
    detections_count = models.IntegerField(null=True, blank=True)

    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name="captures")
    deployment = models.ForeignKey(Deployment, on_delete=models.SET_NULL, null=True, related_name="captures")
    event = models.ForeignKey(
        Event,
        on_delete=models.SET_NULL,
        null=True,
        related_name="captures",
        db_index=True,
        blank=True,
    )

    event_id: int | None
    detections: models.QuerySet["Detection"]
    collections: models.QuerySet["SourceImageCollection"]
    jobs: models.QuerySet["Job"]

    objects = SourceImageManager()

    def __str__(self) -> str:
        return f"{self.__class__.__name__} #{self.pk} {self.path}"

    def public_url(self, raise_errors=False) -> str | None:
        """
        Return the public URL for this image.

        The base URL is determined by the deployment's data source and is cached
        on the source image. If the deployment's data source changes, the URLs
        for all source images will be updated.

        @TODO add support for thumbnail URLs here?
        @TODO consider if we ever need to access the original image directly!
        @TODO every source image request requires joins for the deployment and data source, is this necessary?
        """
        # Get presigned URL if access keys are configured
        data_source = self.deployment.data_source if self.deployment and self.deployment.data_source else None
        if (
            data_source is not None
            and not data_source.public_base_url
            and data_source.access_key
            and data_source.secret_key
        ):
            url = ami.utils.s3.get_presigned_url(data_source.config, key=self.path)
        elif self.public_base_url:
            url = urllib.parse.urljoin(self.public_base_url, self.path.lstrip("/"))
        else:
            msg = f"Public URL for {self} is not available. Public base URL: '{self.public_base_url}'"
            if raise_errors:
                raise ValueError(msg)
            else:
                logger.error(msg)
                return None
        # Ensure url has a scheme
        if not urllib.parse.urlparse(url).netloc:
            msg = f"Public URL for {self} is invalid: {url}. Public base URL: '{self.public_base_url}'"
            if raise_errors:
                raise ValueError(msg)
            else:
                logger.error(msg)
                return None
        else:
            return url

    # backwards compatibility
    url = public_url

    def size_display(self) -> str:
        """
        Return the size of the image in human-readable format.
        """
        if self.size is None:
            return filesizeformat(0)
        else:
            return filesizeformat(self.size)

    def get_detections_count(self) -> int:
        return self.detections.distinct().count()

    def get_base_url(self) -> str | None:
        """
        Determine the public URL from the deployment's data source.

        If there is no data source, return None

        If the public_base_url is None, a presigned URL will be generated for each request.
        """
        if self.deployment and self.deployment.data_source and self.deployment.data_source.public_base_url:
            return self.deployment.data_source.public_base_url
        else:
            return None

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

    def event_next_capture_id(self) -> int | None:
        """
        Return the next capture in the event.

        This should be populated by the query in the ViewSet
        but here is the query for reference:
        return SourceImage.objects.filter(
        event=self.event, timestamp__gt=self.timestamp).order_by("timestamp").values("id").first()
        """
        return None

    def event_prev_capture_id(self) -> int | None:
        """
        Return the previous capture in the event.

        This will be populated by the query in the ViewSet but here is the query for reference:
        return SourceImage.objects.filter(
        event=self.event, timestamp__lt=self.timestamp).order_by("-timestamp").values("id").first()
        """
        return None

    def event_current_capture_index(self) -> int | None:
        """
        Return the index of the current capture in the event.

        This will be populated by the query in the ViewSet but here is the query for reference:
        return SourceImage.objects.filter(
        event=self.event, timestamp__lt=self.timestamp).count()
        or using window functions:
        return SourceImage.objects.filter(
            event=self.event, timestamp__lt=self.timestamp).annotate(
            index=models.Window(
            expression=models.functions.RowNumber(),
            order_by=models.F("timestamp").desc(),
        )
        ).values("index").first()
        """
        return None

    def event_total_captures(self) -> int | None:
        """
        Return the total number of captures in the event.

        This will be populated by the query in the ViewSet but here is the query for reference:
        return SourceImage.objects.filter(event=self.event).count()

        These values are used to help navigate between images in the event.

        @TODO Can we remove these methods? Seems to be a requirement for DRF serializers.
        """
        return None

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

    def occurrences_count(self) -> int | None:
        # This should always be pre-populated using queryset annotations
        return None

    def taxa_count(self) -> int | None:
        # This should always be pre-populated using queryset annotations
        return None

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


def update_detection_counts(qs: models.QuerySet[SourceImage] | None = None, null_only=False) -> int:
    """
    Update the detection count for all source images using a bulk update query.

    @TODO Needs testing.
    """
    qs = qs or SourceImage.objects.all()
    if null_only:
        qs = qs.filter(detections_count__isnull=True)

    subquery = models.Subquery(
        Detection.objects.filter(source_image_id=models.OuterRef("pk"))
        .values("source_image_id")
        .annotate(count=models.Count("id"))
        .values("count"),
        output_field=models.IntegerField(),
    )
    start_time = time.time()
    # Use Coalesce to default to 0 instead of NULL
    num_updated = qs.update(detections_count=models.functions.Coalesce(subquery, models.Value(0)))
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
    minute_interval: int,
    qs: models.QuerySet[SourceImage],
    max_num: int | None = None,
) -> typing.Generator[SourceImage, None, None]:
    """
    Return a sample of captures from the deployment, evenly spaced apart by minute_interval.
    """

    last_capture = None
    total = 0

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
    qs: models.QuerySet[SourceImage],
) -> typing.Generator[SourceImage | None, None, None]:
    """
    Return the n-th position capture from each event.

    For example if position = 0, the first capture from each event will be returned.
    If position = -1, the last capture from each event will be returned.
    """

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
    qs: models.QuerySet[SourceImage],
) -> typing.Generator[SourceImage, None, None]:
    """
    Return every nth capture from each event.

    For example if nth = 1, every capture from each event will be returned.
    If nth = 5, every 5th capture from each event will be returned.
    """

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

    def get_project(self):
        return self.occurrence.get_project()

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


class ClassificationQuerySet(models.QuerySet):
    def find_duplicates(self, project_id: int | None = None) -> models.QuerySet:
        # Find the oldest classification for each unique combination
        if project_id:
            self = self.filter(detection__source_image__project_id=project_id)
        unique_oldest = (
            self.values("detection", "taxon", "algorithm", "score", "softmax_output", "raw_output")
            .annotate(min_id=models.Min("id"))
            .distinct()
        )

        # Keep only the oldest classifications
        return self.exclude(id__in=[item["min_id"] for item in unique_oldest])


class ClassificationManager(models.Manager.from_queryset(ClassificationQuerySet)):
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

    taxon = models.ForeignKey("Taxon", on_delete=models.SET_NULL, null=True, related_name="classifications")
    score = models.FloatField(null=True)
    timestamp = models.DateTimeField()
    terminal = models.BooleanField(
        default=True, help_text="Is this the final classification from a series of classifiers in a pipeline?"
    )
    logits = ArrayField(
        models.FloatField(), null=True, help_text="The raw output of the last fully connected layer of the model"
    )
    scores = ArrayField(
        models.FloatField(),
        null=True,
        help_text="The probabilities the model, calibrated by the model maker, likely the softmax output",
    )
    category_map = models.ForeignKey("ml.AlgorithmCategoryMap", on_delete=models.PROTECT, null=True)

    algorithm = models.ForeignKey(
        "ml.Algorithm",
        on_delete=models.SET_NULL,
        null=True,
        related_name="classifications",
    )
    # job = models.CharField(max_length=255, null=True)

    objects = ClassificationManager()

    # Type hints for auto-generated fields
    taxon_id: int
    algorithm_id: int

    class Meta:
        ordering = ["-created_at", "-score"]

    def __str__(self) -> str:
        terminal = "Terminal" if self.terminal else "Intermediate"
        if logger.getEffectiveLevel() == logging.DEBUG:
            # Query the related objects to get the names
            return f"#{self.pk} to Taxon {self.taxon} ({self.score:.2f}) by Algorithm {self.algorithm} ({terminal})"
        return (
            f"#{self.pk} to Taxon #{self.taxon_id} ({self.score:.2f}) by Algorithm #{self.algorithm_id} ({terminal})"
        )

    def top_scores_with_index(self, n: int | None = None) -> typing.Iterable[tuple[int, float]]:
        """
        Return the scores with their index, but sorted by score.
        """
        if self.scores:
            top_scores_by_index = sorted(enumerate(self.scores), key=lambda x: x[1], reverse=True)[:n]
            return top_scores_by_index
        else:
            return []

    def predictions(self, sort=True) -> typing.Iterable[tuple[str, float]]:
        """
        Return all label-score pairs for this classification using the category map.
        """
        if not self.category_map:
            raise ValueError("Classification must have a category map to get predictions.")
        scores = self.scores or []
        preds = zip(self.category_map.labels, scores)
        if sort:
            return sorted(preds, key=lambda x: x[1], reverse=True)
        else:
            return preds

    def predictions_with_taxa(self, sort=True) -> typing.Iterable[tuple["Taxon", float]]:
        """
        Return taxa objects and their scores for this classification using the category map.

        @TODO make this more efficient with numpy and/or postgres array functions. especially when we only need
        the top N out of thousands of taxa.
        """
        if not self.category_map:
            raise ValueError("Classification must have a category map to get predictions.")
        scores = self.scores or []
        category_data_with_taxa = self.category_map.with_taxa()
        taxa_sorted_by_index = [cat["taxon"] for cat in sorted(category_data_with_taxa, key=lambda cat: cat["index"])]
        preds = zip(taxa_sorted_by_index, scores)
        if sort:
            return sorted(preds, key=lambda x: x[1], reverse=True)
        else:
            return preds

    def taxa(self) -> typing.Iterable["Taxon"]:
        """
        Return the taxa objects for this classification using the category map.
        """
        if not self.category_map:
            return []
        category_data_with_taxa = self.category_map.with_taxa()
        taxa_sorted_by_index = [cat["taxon"] for cat in sorted(category_data_with_taxa, key=lambda cat: cat["index"])]
        return taxa_sorted_by_index

    def top_n(self, n: int = 3) -> list[dict[str, "Taxon | float | None"]]:
        """Return top N taxa and scores for this classification."""
        if not self.category_map:
            raise ValueError("Classification must have a category map to get top N.")

        top_scored = self.top_scores_with_index(n)  # (index, score) pairs
        indexes = [idx for idx, _ in top_scored]
        category_data = self.category_map.with_taxa(only_indexes=indexes)
        index_to_taxon = {cat["index"]: cat["taxon"] for cat in category_data}

        return [
            {
                "taxon": index_to_taxon[i],
                "score": s,
                "logit": self.logits[i] if self.logits else None,
            }
            for i, s in top_scored
        ]

    def save(self, *args, **kwargs):
        """
        Set the category map based on the algorithm.
        """
        if self.algorithm and not self.category_map:
            self.category_map = self.algorithm.category_map
        super().save(*args, **kwargs)


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
    path = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=(
            "Either a full URL to a cropped detection image or a relative path to a file in the default "
            "project storage. @TODO ensure all detection crops are hosted in the project storage, "
            "not the default media storage. Migrate external URLs."
        ),
    )

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
    # Time that the detection was created by the algorithm in the processing service
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

    # For type hints
    classifications: models.QuerySet["Classification"]
    source_image_id: int
    detection_algorithm_id: int

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


class OccurrenceQuerySet(models.QuerySet["Occurrence"]):
    def valid(self):
        return self.exclude(detections__isnull=True)

    def with_detections_count(self):
        return self.annotate(detections_count=models.Count("detections", distinct=True))

    def with_timestamps(self):
        """
        These are timestamps used for filtering and ordering in the UI.
        """
        return self.annotate(
            first_appearance_timestamp=models.Min("detections__timestamp"),
            last_appearance_timestamp=models.Max("detections__timestamp"),
            first_appearance_time=models.Min("detections__timestamp__time"),
            duration=models.ExpressionWrapper(
                models.F("last_appearance_timestamp") - models.F("first_appearance_timestamp"),
                output_field=models.DurationField(),
            ),
        )

    def with_identifications(self):
        return self.prefetch_related(
            "identifications",
            "identifications__taxon",
            "identifications__user",
        )

    def unique_taxa(self, project: Project | None = None):
        qs = self
        if project:
            qs = self.filter(project=project)
        qs = (
            qs.filter(determination__isnull=False, event__isnull=False)
            .order_by("determination_id")
            .distinct("determination_id")
        )
        return qs


class OccurrenceManager(models.Manager.from_queryset(OccurrenceQuerySet)):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "determination",
                "deployment",
                "project",
            )
        )


@final
class Occurrence(BaseModel):
    """An occurrence of a taxon, a sequence of one or more detections"""

    # @TODO change Determination to a nested field with a Taxon, User, Identification, etc like the serializer
    # this could be a OneToOneField to a Determination model or a JSONField validated by a Pydantic model
    determination = models.ForeignKey("Taxon", on_delete=models.SET_NULL, null=True, related_name="occurrences")
    determination_score = models.FloatField(null=True, blank=True)

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
        for path in (
            Detection.objects.filter(occurrence=self).exclude(path=None).values_list("path", flat=True)[:limit]
        ):
            yield get_media_url(path)

    @functools.cached_property
    def best_detection(self):
        return Detection.objects.filter(occurrence=self).order_by("-classifications__score").first()

    @functools.cached_property
    def best_prediction(self):
        """
        Use the best prediction as the best identification if there are no human identifications.

        Uses the highest scoring classification (from any algorithm) as the best prediction.
        Considers terminal classifications first, then non-terminal ones.
        (Terminal classifications are the final classifications of a pipeline, non-terminal are intermediate models.)
        """
        return self.predictions().order_by("-terminal", "-score").first()

    @functools.cached_property
    def best_identification(self):
        """
        The most recent human identification is used as the best identification.

        @TODO this could use a confidence level chosen manually by the users/experts.
        """
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
            # @TODO remove
            self.determination_score = self.get_determination_score()
            if not self.determination_score:
                logger.warning(f"Could not determine score for {self}")
            else:
                self.save(update_determination=False)

    class Meta:
        ordering = ["-determination_score"]


def update_occurrence_determination(
    occurrence: Occurrence, current_determination: typing.Optional["Taxon"] = None, save=True
) -> bool:
    """
    Update the determination of the occurrence based on the identifications & predictions.

    If there are identifications, set the determination to the latest identification.
    If there are no identifications, set the determination to the top prediction.

    The `current_determination` is the determination currently saved in the database.
    The `occurrence` object may already have a different un-saved determination set
    so it is necessary to retrieve the current determination from the database, but
    this can also be passed in as an argument to avoid an extra database query.

    @TODO Add tests for this important method!
    """
    needs_update = False

    # Invalidate the cached properties so they will be re-calculated
    if hasattr(occurrence, "best_identification"):
        del occurrence.best_identification
    if hasattr(occurrence, "best_prediction"):
        del occurrence.best_prediction
    if hasattr(occurrence, "best_identification"):
        del occurrence.best_identification

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
        logger.debug(f"Changing det. of {occurrence} from {current_determination} to {new_determination}")
        occurrence.determination = new_determination
        needs_update = True

    if new_score and new_score != occurrence.determination_score:
        logger.debug(f"Changing det. score of {occurrence} from {occurrence.determination_score} to {new_score}")
        occurrence.determination_score = new_score
        needs_update = True

    if not needs_update:
        if logger.getEffectiveLevel() <= logging.DEBUG:
            all_predictions = occurrence.predictions()
            all_preds_print = ", ".join([str(p) for p in all_predictions])
            logger.debug(
                f"No update needed for determination of {occurrence}. Best prediction: {occurrence.best_prediction}. "
                f"All preds: {all_preds_print}"
            )

    if save and needs_update:
        occurrence.save(update_determination=False)

    return needs_update


class TaxonQuerySet(models.QuerySet):
    def with_occurrence_counts(self, project: Project):
        """
        Annotate each taxon with the count of its occurrences for a given project.
        """
        qs = self
        qs = qs.filter(occurrences__project=project)

        return qs.annotate(occurrence_count=models.Count("occurrences", distinct=True))


@final
class TaxonManager(models.Manager.from_queryset(TaxonQuerySet)):
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

    def update_all_parents(self):
        """Efficiently update all parents for all taxa."""
        taxa = self.get_queryset().select_related("parent")
        logging.info(f"Updating the cached parent tree for {taxa.count()} taxa")

        # Build a dictionary of taxon parents
        parents = {taxon.id: taxon.parent_id for taxon in taxa}

        # Precompute all parents in a single pass
        all_parents = {}
        for taxon_id in parents:
            if taxon_id not in all_parents:
                taxon_parents = []
                current_id = taxon_id
                while current_id in parents:
                    current_id = parents[current_id]
                    taxon_parents.append(current_id)
                all_parents[taxon_id] = taxon_parents

        # Prepare bulk update data
        bulk_update_data = []
        for taxon in taxa:
            taxon_parents = all_parents[taxon.id]
            parent_taxa = list(taxa.filter(id__in=taxon_parents))
            taxon_parents = [
                TaxonParent(
                    id=taxon.id,
                    name=taxon.name,
                    rank=taxon.rank,
                )
                for taxon in parent_taxa
            ]
            taxon_parents.sort(key=lambda t: t.rank)

            bulk_update_data.append(taxon)

        # Perform bulk update
        # with transaction.atomic():
        #     self.bulk_update(bulk_update_data, ["parents_json"], batch_size=1000)
        # There is a bug that causes the bulk update to fail with a custom JSONField
        # https://code.djangoproject.com/ticket/35167
        # So we have to update each taxon individually
        for taxon in bulk_update_data:
            taxon.save(update_fields=["parents_json"])

        logging.info(f"Updated parents for {len(bulk_update_data)} taxa")

    def with_children(self):
        qs = self.get_queryset()
        # Add Taxon that are children of this Taxon using parents_json field (not direct_children)

        # example for single taxon:
        taxon = Taxon.objects.get(pk=1)
        taxa = Taxon.objects.filter(parents_json__contains=[{"id": taxon.id}])
        # add them to the queryset
        qs = qs.annotate(children=models.Subquery(taxa.values("id")))
        return qs

    def with_occurrence_counts(self) -> models.QuerySet:
        """
        Count the number of occurrences for a taxon and all occurrences of the taxon's children.

        @TODO Try a recursive CTE in a raw SQL query,
        or count the occurrences in a separate query and attach them to the Taxon objects.
        """

        raise NotImplementedError(
            "Occurrence counts can not be calculated in a subquery with the current JSONField schema. "
            "Fetch them per taxon."
        )


class TaxonParent(pydantic.BaseModel):
    """
    Should contain all data needed for TaxonParentSerializer

    Needs a custom encoder and decoder for for the TaxonRank enum
    because it is an OrderedEnum and not a standard str Enum.
    """

    id: int
    name: str
    rank: TaxonRank

    class Config:
        # Make sure the TaxonRank is retrieved as an object and not a string
        # so we can sort by rank. The DRF serializer will convert it to a string.
        # just for the API responses.
        use_enum_values = False


@final
class Taxon(BaseModel):
    """A taxonomic classification"""

    name = models.CharField(max_length=255, unique=True)
    display_name = models.CharField("Cached display name", max_length=255, null=True, blank=True, unique=True)
    rank = models.CharField(max_length=255, choices=TaxonRank.choices(), default=TaxonRank.SPECIES.name)
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="direct_children"
    )

    # Examples how to query this JSON array field
    # Taxon.objects.filter(parents_json__contains=[{"id": 1}])
    # https://stackoverflow.com/a/53942463/966058
    parents_json = SchemaField(list[TaxonParent], null=False, blank=True, default=list)

    active = models.BooleanField(default=True)
    synonym_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="synonyms")

    common_name_en = models.CharField(max_length=255, blank=True, null=True)

    search_names = ArrayField(models.CharField(max_length=255), null=True, blank=True)
    gbif_taxon_key = models.BigIntegerField("GBIF taxon key", blank=True, null=True)
    bold_taxon_bin = models.CharField("BOLD taxon BIN", max_length=255, blank=True, null=True)
    inat_taxon_id = models.BigIntegerField("iNaturalist taxon ID", blank=True, null=True)
    # lepsai_id = models.BigIntegerField("LepsAI / Fieldguide ID", blank=True, null=True)

    notes = models.TextField(blank=True)

    projects = models.ManyToManyField("Project", related_name="taxa")
    direct_children: models.QuerySet["Taxon"]
    occurrences: models.QuerySet[Occurrence]
    classifications: models.QuerySet["Classification"]
    lists: models.QuerySet["TaxaList"]

    author = models.CharField(max_length=255, blank=True)
    authorship_date = models.DateField(null=True, blank=True, help_text="The date the taxon was described.")
    ordering = models.IntegerField(null=True, blank=True)
    sort_phylogeny = models.BigIntegerField(blank=True, null=True)

    objects: TaxonManager = TaxonManager()

    # Type hints for auto-generated fields
    parent_id: int | None

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
        # Use the parents_json field to get all children
        return Taxon.objects.filter(parents_json__contains=[{"id": self.pk}]).count()

    def occurrences_count(self) -> int:
        # return self.occurrences.count()
        return 0

    def occurrences_count_recursive(self) -> int:
        """
        Use the parents_json field to get all children, count their occurrences and sum them.
        """
        return (
            Taxon.objects.filter(models.Q(models.Q(parents_json__contains=[{"id": self.pk}]) | models.Q(id=self.pk)))
            .annotate(occurrences_count=models.Count("occurrences"))
            .aggregate(models.Sum("occurrences_count"))["occurrences_count__sum"]
            or 0
        )

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

    def occurrence_images(self, limit: int | None = 10) -> list[str]:
        # This is handled by an annotation if we are filtering by project, deployment or event
        return []

    def get_occurrence_images(
        self,
        limit: int | None = 10,
        project_id: int | None = None,
        classification_threshold: float = 0,
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
        Populate the cached `parents_json` list by recursively following the `parent` field.

        @TODO this requires all of the taxon's parent taxa to have the `parent` attribute set correctly.
        """

        current_taxon = self
        parents = []
        logger.debug(f"Updating parents for {current_taxon} (#{current_taxon.pk})")
        while current_taxon.parent is not None:
            taxon_parent = TaxonParent(
                id=current_taxon.parent.id,
                name=current_taxon.parent.name,
                rank=current_taxon.parent.rank,
            )
            logger.debug(f"Adding parent {taxon_parent} to {current_taxon} (#{current_taxon.pk}) in parents_json")
            parents.append(taxon_parent)
            current_taxon = current_taxon.parent
        # Sort parents by rank using ordered enum
        parents = sorted(parents, key=lambda t: t.rank)
        self.parents_json = parents
        if save:
            self.save()

        return parents

    def update_search_names(self, save=False):
        """
        Add common names to the search names list.

        @TODO add synonyms and other names to the search names list.
        """
        search_names = self.search_names or []
        common_name_field_names = [field.name for field in self._meta.fields if field.name.startswith("common_name_")]
        for field_name in common_name_field_names:
            common_name = getattr(self, field_name)
            if common_name:
                search_names.append(common_name)
        self.search_names = list(set(search_names))
        if save:
            self.save(update_fields=["search_names"])

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

    def update_calculated_fields(self, save=False):
        self.display_name = self.get_display_name()
        self.update_parents(save=False)
        self.update_search_names(save=False)
        if save:
            self.save(update_calculated_fields=False)

    def save(self, update_calculated_fields=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if update_calculated_fields:
            self.update_calculated_fields(save=True)


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


class SourceImageCollectionQuerySet(models.QuerySet):
    def with_source_images_count(self):
        return self.annotate(
            source_images_count=models.Count(
                "images",
                distinct=True,
            )
        )

    def with_source_images_with_detections_count(self):
        return self.annotate(
            source_images_with_detections_count=models.Count(
                "images", filter=models.Q(images__detections__isnull=False), distinct=True
            )
        )

    def with_source_images_processed_by_algorithm_count(self, algorithm_id: int):
        return self.annotate(
            source_images_processed_by_algorithm_count=models.Count(
                "images",
                filter=models.Q(images__detections__classifications__algorithm_id=algorithm_id),
                distinct=True,
            )
        )

    def with_occurrences_count(self, classification_threshold: float = 0):
        return self.annotate(
            occurrences_count=models.Count(
                "images__detections__occurrence",
                filter=models.Q(
                    images__detections__occurrence__determination_score__gte=classification_threshold,
                ),
                distinct=True,
            )
        )

    def with_taxa_count(self, classification_threshold: float = 0):
        return self.annotate(
            taxa_count=models.Count(
                "images__detections__occurrence__determination",
                distinct=True,
                filter=models.Q(
                    images__detections__occurrence__determination_score__gte=classification_threshold,
                ),
            )
        )


class SourceImageCollectionManager(models.Manager):
    def get_queryset(self) -> SourceImageCollectionQuerySet:
        return SourceImageCollectionQuerySet(self.model, using=self._db)


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
    # dataset_type = models.CharField(
    #     max_length=255,
    #     choices=as_choices(["Curated", "Dynamic", "Sampling"]),
    # )
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

    objects = SourceImageCollectionManager()

    jobs: models.QuerySet["Job"]

    def infer_dataset_type(self):
        if "starred" in self.name.lower():
            return "curated"
        else:
            return "sampling"

    @property
    def dataset_type(self):
        return self.infer_dataset_type()

    def source_images_count(self) -> int | None:
        # This should always be pre-populated using queryset annotations
        # return self.images.count()
        return None

    def source_images_with_detections_count(self) -> int | None:
        # This should always be pre-populated using queryset annotations
        # return self.images.filter(detections__isnull=False).count()
        return None

    def occurrences_count(self) -> int | None:
        # This should always be pre-populated using queryset annotations
        return None

    def taxa_count(self) -> int | None:
        # This should always be pre-populated using queryset annotations
        return None

    def get_queryset(self):
        return SourceImage.objects.filter(project=self.project)

    @classmethod
    def sampling_methods(cls):
        return [method for method in dir(cls) if method.startswith("sample_")]

    def populate_sample(self, job: "Job | None" = None):
        """Create a sample of source images based on the method and kwargs"""
        kwargs = self.kwargs or {}

        if job:
            task_logger = job.logger
        else:
            task_logger = logger

        method_name = f"sample_{self.method}"
        if not hasattr(self, method_name):
            raise ValueError(f"Invalid sampling method: {self.method}. Choices are: {_SOURCE_IMAGE_SAMPLING_METHODS}")
        else:
            task_logger.info(f"Sampling using method '{method_name}' with params: {kwargs}")
            method = getattr(self, method_name)
            task_logger.info(f"Sampling and saving captures to {self}")
            self.images.set(method(**kwargs))
            self.save()
            task_logger.info(f"Done sampling and saving captures to {self}")

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
        max_num: int | None = None,
        shuffle: bool = True,  # This is applicable if max_num is set and minute_interval is not set
        hour_start: int | None = None,
        hour_end: int | None = None,
        month_start: int | None = None,
        month_end: int | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        deployment_ids: list[int] | None = None,
    ) -> models.QuerySet | typing.Generator[SourceImage, None, None]:
        qs = self.get_queryset()

        if deployment_ids is not None:
            qs = qs.filter(deployment__in=deployment_ids)
        if date_start is not None:
            qs = qs.filter(timestamp__date__gte=DateStringField.to_date(date_start))
        if date_end is not None:
            qs = qs.filter(timestamp__date__lte=DateStringField.to_date(date_end))

        if month_start is not None:
            qs = qs.filter(timestamp__month__gte=month_start)
        if month_end is not None:
            qs = qs.filter(timestamp__month__lte=month_end)

        if hour_start is not None and hour_end is not None:
            if hour_start < hour_end:
                # Hour range within the same day (e.g., 08:00 to 15:00)
                qs = qs.filter(timestamp__hour__gte=hour_start, timestamp__hour__lte=hour_end)
            else:
                # Hour range has Midnight crossover: (e.g., 17:00 to 06:00)
                qs = qs.filter(models.Q(timestamp__hour__gte=hour_start) | models.Q(timestamp__hour__lte=hour_end))
        elif hour_start is not None:
            qs = qs.filter(timestamp__hour__gte=hour_start)
        elif hour_end is not None:
            qs = qs.filter(timestamp__hour__lte=hour_end)

        if minute_interval is not None:
            # @TODO can this be done in the database and return a queryset?
            # this currently returns a list of source images
            # Ensure the queryset is limited to the project
            qs = qs.filter(project=self.project)
            qs = sample_captures_by_interval(minute_interval=minute_interval, qs=qs, max_num=max_num)
        else:
            if max_num is not None:
                if shuffle:
                    qs = qs.order_by("?")
                qs = qs[:max_num]

        return qs

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
        qs = qs.filter(project=self.project)
        return sample_captures_by_interval(minute_interval=minute_interval, qs=qs)

    def sample_positional(self, position: int = -1):
        """Sample the single nth source image from all events in the project"""

        qs = self.get_queryset()
        return sample_captures_by_position(position=position, qs=qs)

    def sample_nth(self, nth: int):
        """Sample every nth source image from all events in the project"""

        qs = self.get_queryset()
        return sample_captures_by_nth(nth=nth, qs=qs)

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
