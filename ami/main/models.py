import contextlib
import datetime
import functools
import logging
import operator
import textwrap
import typing
import uuid
from io import BytesIO
from typing import Final, final  # noqa: F401

import PIL.Image
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import IntegrityError, models
from django.db.models import Q
from django.db.models.fields.files import ImageFieldFile
from django.template.defaultfilters import filesizeformat
from django.utils import timezone
from rest_framework.request import Request

import ami.tasks
import ami.utils
from ami.base.models import BaseModel, BaseQuerySet
from ami.main import charts

# These models and enums must be re-exported so that they are referenced as
# models.* for compatibility with migrations existing before this change.
from ami.main.models_future.enums import DEFAULT_RANKS, TaxonRank  # noqa: F401
from ami.main.models_future.filters import build_occurrence_default_filters_q
from ami.main.models_future.identifications import Identification  # noqa: F401
from ami.main.models_future.images import (  # noqa: F401
    SourceImage,
    SourceImageCollection,
    SourceImageCollectionManager,
    SourceImageCollectionQuerySet,
    SourceImageManager,
    SourceImageQuerySet,
    SourceImageThumbnail,
    update_detection_counts,
)
from ami.main.models_future.occurrences import (  # noqa: F401
    BEST_IDENTIFICATION_ORDER,
    BEST_MACHINE_PREDICTION_ORDER,
    Occurrence,
    OccurrenceManager,
    OccurrenceQuerySet,
    update_occurrence_determination,
)
from ami.main.models_future.projects import (  # noqa: F401
    _POST_TITLE_MAX_LENGTH,
    Project,
    ProjectFeatureFlags,
    ProjectManager,
    ProjectQuerySet,
    ProjectSettingsMixin,
    get_default_feature_flags,
)
from ami.main.models_future.storage import (  # noqa: F401
    S3StorageSource,
    SourceImageUpload,
    delete_source_image,
    upload_to_with_deployment,
)
from ami.main.models_future.taxonomy import (  # noqa: F401
    Tag,
    TaxaList,
    TaxaListManager,
    TaxaListQuerySet,
    Taxon,
    TaxonManager,
    TaxonParent,
    TaxonQuerySet,
    verified_taxon_counts,
)
from ami.ml.schemas import BoundingBox
from ami.users.models import User
from ami.utils.media import calculate_file_checksum, extract_timestamp

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job

logger = logging.getLogger(__name__)


def bbox_is_null(bbox) -> bool:
    """In-memory equivalent of null_detections_q() for an already-fetched bbox value."""
    return bbox is None


def null_detections_q(prefix: str = "") -> Q:
    """
    Return a Q expression matching null-marker Detection rows, optionally prefixed
    for use across relations (e.g. null_detections_q("images__detections__") for an
    aggregate filter on a parent table). For Detection queries directly, prefer
    Detection.objects.null_markers() / .valid() instead.

    Null markers are stored as SQL NULL (bbox IS NULL); that is the only sentinel form.
    """
    return Q(**{f"{prefix}bbox__isnull": True})


# Single source of truth for "this Detection is a null marker", shared by
# DetectionQuerySet.valid() / .null_markers(). Defined via null_detections_q() so the
# constant and the helper cannot drift apart.
NULL_DETECTIONS_FILTER = null_detections_q()


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


def get_or_create_default_device(project: "Project") -> "Device":
    """Create a default device for a project."""
    device, _created = Device.objects.get_or_create(name="Default Device", project=project)
    logger.info(f"Created default device for project {project}")
    return device


def get_or_create_default_research_site(project: "Project") -> "Site":
    """Create a default research site for a project."""
    site, _created = Site.objects.get_or_create(name="Default Site", project=project)
    logger.info(f"Created default research site for project {project}")
    return site


def get_or_create_default_deployment(
    project: "Project", site: "Site | None" = None, device: "Device | None" = None
) -> "Deployment":
    """Create a default deployment for a project."""
    deployment, _created = Deployment.objects.get_or_create(
        name="Default Station",
        project=project,
        research_site=site,
        device=device,
        latitude=0,
        longitude=0,
    )
    logger.info(f"Created default deployment for project {project}")
    return deployment


def get_or_create_default_collection(project: "Project") -> "SourceImageCollection":
    """
    Create a default collection for a project for all images.

    @TODO Consider ways to update this collection automatically. With a query-only collection
    or a periodic task that runs the populate_collection method.
    """
    collection, _created = SourceImageCollection.objects.get_or_create(
        name="All Images",
        project=project,
        method="full",
    )
    logger.info(f"Created default capture set for project {project}")
    return collection


def get_project_default_filters():
    """
    Read default taxa names from Django settings (read from environment variables)
    and return corresponding Taxon objects.
    """
    include_taxa = list(Taxon.objects.filter(name__in=settings.DEFAULT_INCLUDE_TAXA))
    exclude_taxa = list(Taxon.objects.filter(name__in=settings.DEFAULT_EXCLUDE_TAXA))

    return {"default_include_taxa": include_taxa, "default_exclude_taxa": exclude_taxa}


def get_or_create_default_project(user: User) -> "Project":
    """
    Create a default project for a user.

    When a new project is created, default related objects (device, site,
    deployment, collection, processing service) and default taxa filters are
    initialized explicitly. ``get_or_create`` bypasses ``ProjectManager.create``,
    so we call ``create_related_defaults`` here instead of relying on the manager.
    """
    project, created = Project.objects.get_or_create(name="Scratch Project", owner=user)
    if created:
        logger.info(f"Created default project for user {user}")
        Project.objects.create_related_defaults(project)
        defaults = get_project_default_filters()

        if defaults["default_include_taxa"]:
            project.default_filters_include_taxa.set(defaults["default_include_taxa"])
            logger.info(f"Set {len(defaults['default_include_taxa'])} default include taxa for project {project}")
        if defaults["default_exclude_taxa"]:
            project.default_filters_exclude_taxa.set(defaults["default_exclude_taxa"])
            logger.info(f"Set {len(defaults['default_exclude_taxa'])} default exclude taxa for project {project}")
        project.save()
    else:
        logger.info(f"Loaded existing default project for user {user}")
    return project


def add_taxa_counts(projects: list["Project"]) -> None:
    """
    Set `taxa_observed_count` on each project: its distinct taxa after its own default filters,
    the number the project summary shows.

    Each project has its own filters, so this is one grouped query over a page of projects
    rather than an annotation, and the count cannot be sorted on.
    """
    from ami.main.models_future.filters import build_occurrence_default_filters_q

    if not projects:
        return
    models.prefetch_related_objects(projects, "default_filters_include_taxa", "default_filters_exclude_taxa")
    in_scope = functools.reduce(
        operator.or_, (Q(project=project) & build_occurrence_default_filters_q(project) for project in projects)
    )
    # The same conditions as OccurrenceQuerySet.unique_taxa().
    counts = dict(
        Occurrence.objects.filter(in_scope, determination__isnull=False, event__isnull=False)
        .values("project")
        .annotate(taxa=models.Count("determination", distinct=True))
        .values_list("project", "taxa")
    )
    for project in projects:
        project.taxa_observed_count = counts.get(project.pk, 0)


class UserProjectMembership(BaseModel):
    """
    Through model connecting User <-> Project.
    This model represents membership ONLY.
    Role assignment is handled separately via permission groups.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="project_memberships",
    )

    project = models.ForeignKey(
        "main.Project",
        on_delete=models.CASCADE,
        related_name="project_memberships",
    )

    def check_permission(self, user: AbstractUser | AnonymousUser, action: str) -> bool:
        project = self.project
        # Allow viewing membership details if the user has view permission on the project
        if action == "retrieve":
            return user.has_perm(Project.Permissions.VIEW_USER_PROJECT_MEMBERSHIP, project)
        # Allow users to delete their own membership
        if action == "destroy" and user == self.user:
            return True
        return super().check_permission(user, action)

    def get_user_object_permissions(self, user) -> list[str]:
        # Return delete permission if user is the same as the membership user
        user_permissions = super().get_user_object_permissions(user)
        if user == self.user:
            if "delete" not in user_permissions:
                user_permissions.append("delete")
        return user_permissions

    class Meta:
        unique_together = ("user", "project")


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
class DeploymentManager(models.Manager.from_queryset(ProjectQuerySet)):
    """
    Custom manager that adds counts of related objects to the default queryset.
    """

    pass


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

    def get_detections_count(self) -> int | None:
        """
        Return detections count filtered by project default filters.

        Excludes null-bbox placeholder detections (records indicating an image
        was processed and no detections were found) to stay consistent with
        ``SourceImage.get_detections_count`` and ``Event.get_detections_count``.
        """
        qs = Detection.objects.filter(source_image__deployment=self).valid()
        filter_q = build_occurrence_default_filters_q(
            project=self.project,
            request=None,
            occurrence_accessor="occurrence",
        )

        return qs.filter(filter_q).distinct().count()

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

    def sync_captures(
        self,
        batch_size=1000,
        regroup_events_per_batch=False,
        regroup_after=True,
        job: "Job | None" = None,
    ) -> int:
        """
        Import images from the deployment's data source.

        Set ``regroup_after=False`` when the caller (e.g. ``DataStorageSyncJob``)
        will run regrouping as a tracked stage of its own so the work is visible
        in the Jobs UI instead of buried inside ``Deployment.save()``.
        """

        deployment = self
        assert deployment.data_source, f"Deployment {deployment.name} has no data source configured"

        s3_config = deployment.data_source.config
        total_size = 0
        total_files = 0
        failed = 0
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
            try:
                source_image = _create_source_image_for_sync(deployment, obj)
            except Exception:
                failed += 1
                msg = f"Failed to process {obj.get('Key', '?')}"
                if job:
                    job.logger.exception(msg)
                else:
                    logger.exception(msg)
                continue

            if source_image:
                # Skip images with unparseable timestamps — they can't be grouped into events
                if source_image.timestamp is None:
                    failed += 1
                    msg = f"No timestamp parsed from filename: {obj['Key']}"
                    if job:
                        job.logger.error(msg)
                    else:
                        logger.error(msg)
                    continue
                elif source_image.timestamp.year < 2000:
                    msg = f"Suspicious timestamp ({source_image.timestamp.year}) for: {obj['Key']}"
                    if job:
                        job.logger.warning(msg)
                    else:
                        logger.warning(msg)

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
                    job.progress.update_stage(job.job_type().key, total_files=total_files, failed=failed)
                    job.update_progress()

        if source_images:
            # Insert/update the last batch
            _insert_or_update_batch_for_sync(
                deployment, source_images, total_files, total_size, sql_batch_size, regroup_events_per_batch
            )
        if job:
            job.logger.info(f"Processed {total_files} files")
            job.progress.update_stage(job.job_type().key, total_files=total_files, failed=failed)
            job.update_progress()

        _compare_totals_for_sync(deployment, total_files)

        # @TODO decide if we should delete SourceImages that are no longer in the data source

        if regroup_after:
            if job:
                job.logger.info("Saving and recalculating sessions for deployment")
                job.progress.update_stage(job.job_type().key, progress=1)
                job.progress.add_stage("Update deployment cache")
                job.update_progress()

            # If new images were added, ensure the regroup happens now, not queued as an async task.
            self.save(regroup_async=False)

            if job:
                job.progress.update_stage("Update deployment cache", progress=1)
                job.update_progress()
        else:
            # Caller (e.g. DataStorageSyncJob) is responsible for running regroup as
            # an explicit stage. Skip Deployment.save's autoregroup but still
            # refresh cached counts and realign child Event/Occurrence/SourceImage
            # project pointers — those normally run inside Deployment.save's
            # update_calculated_fields branch, which we bypass here.
            self.save(regroup_async=False, update_calculated_fields=False)
            self.update_calculated_fields(save=True)
            if self.project_id:
                self.update_children()

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
        self.detections_count = self.get_detections_count()
        occ_qs = self.occurrences.filter(event__isnull=False).apply_default_filters(  # type: ignore
            project=self.project,
            request=None,
        )  # type: ignore

        self.occurrences_count = occ_qs.distinct().count()

        self.taxa_count = occ_qs.values("determination_id").distinct().count()

        self.first_capture_timestamp, self.last_capture_timestamp = self.get_first_and_last_timestamps()

        if save:
            self.save(update_calculated_fields=False)

    def save(self, update_calculated_fields=True, regroup_async=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.pk and update_calculated_fields:
            if deployment_events_need_update(self):
                logger.info(f"Deployment {self} has events that need to be regrouped")
                if regroup_async:
                    ami.tasks.regroup_events.delay(self.pk)
                else:
                    group_images_into_events(self)
            self.update_calculated_fields(save=True)
            if self.project:
                self.update_children()
                # @TODO this isn't working as a background task
                # ami.tasks.model_task.delay("Project", self.project.pk, "update_children_project")


class EventQuerySet(BaseQuerySet):
    def with_taxa_count(self, project: Project | None = None, request: Request | None = None):
        """
        Annotate each event with the number of distinct taxa observed,
        filtered by default filters (score threshold and taxa inclusion/exclusion).
        """
        if project is None:
            return self

        filter_q = build_occurrence_default_filters_q(project, request, "occurrences")

        return self.annotate(
            taxa_count=models.Count(
                "occurrences__determination",
                distinct=True,
                filter=filter_q,
            )
        )

    def with_occurrences_count(self, project: Project | None = None, request: Request | None = None):
        """
        Annotate each event with the number of occurrences,
        filtered by default filters (score threshold and taxa inclusion/exclusion).
        """
        if project is None:
            return self

        filter_q = build_occurrence_default_filters_q(project, request, "occurrences")

        return self.annotate(
            occurrences_count=models.Count(
                "occurrences",
                distinct=True,
                filter=filter_q,
            )
        )


class EventManager(models.Manager.from_queryset(EventQuerySet)):
    pass


@final
class Event(BaseModel):
    """A monitoring session"""

    reference_type = "session"
    reference_name_field = "name"

    objects: EventManager = EventManager()
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
        """
        Return detections count filtered by project default filters.

        Excludes null-bbox placeholder detections to stay consistent with
        ``SourceImage.get_detections_count`` and ``Deployment.get_detections_count``.
        """
        qs = Detection.objects.filter(source_image__event=self).valid()
        filter_q = build_occurrence_default_filters_q(
            project=self.project,
            request=None,
            occurrence_accessor="occurrence",
        )

        return qs.filter(filter_q).distinct().count()

    def get_occurrences_count(self, classification_threshold: float = 0) -> int:
        """
        Get the count of occurrences for this event, filtered by default filters.

        Note: classification_threshold parameter is deprecated, use project default filters instead.
        """
        return (
            self.occurrences.distinct()
            .apply_default_filters(project=self.project, request=None)  # type: ignore
            .count()
        )

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
        # @TODO these needs to return a source image with detections prefetched and filtered
        # based on the project settings.
        # Ideally this would be an annotated field, rather than an additional query.
        # raise NotImplementedError("This is added an annotated field, it should not be called directly.")
        # return SourceImage.objects.filter(event=self).order_by("timestamp").first().with_detections()
        # with_thumbnails() satisfies the thumbnail_urls prefetch contract for the nested serializer;
        # select_related("project") feeds its project.thumbnails_enabled guard without an extra query.
        return (
            SourceImage.objects.filter(event=self)
            .select_related("project")
            .order_by("timestamp")
            .with_thumbnails()
            .first()
        )

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


def audit_event_lengths(deployment: Deployment):
    logger.info("Checking for unusual event durations")

    events_over_24_hours = Event.objects.filter(
        deployment=deployment, start__lt=models.F("end") - datetime.timedelta(days=1)
    ).count()
    if events_over_24_hours:
        logger.warning(f"Found {events_over_24_hours} event(s) over 24 hours in deployment {deployment}. ")

    events_starting_before_noon = Event.objects.filter(
        deployment=deployment, start__hour__lt=12  # Before hour 12
    ).count()
    if events_starting_before_noon:
        logger.warning(
            f"Found {events_starting_before_noon} event(s) starting before noon in deployment {deployment}. "
        )

    events_ending_before_start = Event.objects.filter(deployment=deployment, start__gt=models.F("end")).count()
    if events_ending_before_start:
        logger.error(f"Found {events_ending_before_start} event(s) with start > end in deployment {deployment}")


DEFAULT_MAX_EVENT_DURATION = datetime.timedelta(hours=24)


# Regroup should finish in seconds, so keep this short: if a worker is killed
# before its finally-block releases the lock, the TTL caps how long it stays held.
# Matches the soft_time_limit on ami.tasks.regroup_events.
REGROUP_LOCK_TTL_SECONDS = 10 * 60


@contextlib.contextmanager
def _regroup_lock(deployment_id: int):
    """
    Acquire a per-deployment lock for regrouping. Token-based release —
    the lock is only deleted if the value we wrote is still there, so an
    expired-then-reacquired-by-someone-else lock doesn't get clobbered.

    Released cleanly on graceful exit and on any exception that propagates
    out of the `with` block (including Celery's `SoftTimeLimitExceeded`).
    Not released on hard worker death (OS SIGKILL, OOM-kill, pod eviction):
    the token lives only in process memory, so a finally block that never
    runs leaves the lock entry sitting until the TTL expires.

    Yields True if acquired (caller should proceed), False if another run
    already holds it (caller should short-circuit).
    """
    from django.core.cache import cache

    lock_key = f"regroup_events:lock:deployment:{deployment_id}"
    token = uuid.uuid4().hex
    acquired = cache.add(lock_key, token, timeout=REGROUP_LOCK_TTL_SECONDS)
    try:
        yield acquired
    finally:
        if acquired:
            current = cache.get(lock_key)
            if current == token:
                cache.delete(lock_key)


def group_images_into_events(
    deployment: Deployment,
    max_time_gap: datetime.timedelta | None = None,
    delete_empty=True,
    max_event_duration: datetime.timedelta | None = DEFAULT_MAX_EVENT_DURATION,
    job: "Job | None" = None,
    stage_key: str | None = None,
) -> list[Event]:
    """
    Group a deployment's captures into Events based on timestamp gaps.

    Holds a per-deployment cache lock so concurrent calls (autoregroup-on-save,
    manual API/admin trigger, sync-time regroup) collapse to a single in-flight
    run rather than racing on the same rows. If the lock is already held, this
    function logs and returns an empty list without touching the DB.

    When ``job`` and ``stage_key`` are passed, summary stats (events created,
    events touched, duplicate-timestamp count, ungrouped captures) are written
    to the named stage so the Jobs UI can surface them. Pure callers (e.g.
    ``Deployment.save`` autoregroup, ``sync_captures`` per-batch) leave both
    arguments at ``None``.
    """
    with _regroup_lock(deployment.pk) as acquired:
        if not acquired:
            msg = f"group_images_into_events skipped for deployment {deployment.pk}: another regroup is in progress."
            if job:
                job.logger.warning(msg)
            else:
                logger.warning(msg)
            return []

        return _group_images_into_events_locked(
            deployment,
            max_time_gap=max_time_gap,
            delete_empty=delete_empty,
            max_event_duration=max_event_duration,
            job=job,
            stage_key=stage_key,
        )


def _group_images_into_events_locked(
    deployment: Deployment,
    max_time_gap: datetime.timedelta | None,
    delete_empty: bool,
    max_event_duration: datetime.timedelta | None,
    job: "Job | None",
    stage_key: str | None,
) -> list[Event]:
    if max_time_gap is None:
        default_gap = datetime.timedelta(minutes=120)
        if deployment.project_id:
            gap_seconds = deployment.project.session_time_gap_seconds
            if gap_seconds is None or gap_seconds <= 0:
                logger.warning(
                    f"Project {deployment.project_id} has invalid session_time_gap_seconds "
                    f"({gap_seconds!r}); falling back to default {default_gap}"
                )
                max_time_gap = default_gap
            else:
                max_time_gap = datetime.timedelta(seconds=gap_seconds)
        else:
            max_time_gap = default_gap
    # Log a warning if multiple SourceImages have the same timestamp
    dupes = (
        SourceImage.objects.filter(deployment=deployment)
        .values("timestamp")
        .annotate(count=models.Count("id"))
        .filter(count__gt=1)
        .exclude(timestamp=None)
    )
    duplicate_timestamp_count = dupes.count()
    if duplicate_timestamp_count:
        sample = "\n".join(
            f'{d.strftime("%Y-%m-%d %H:%M:%S")} x{c}' for d, c in dupes.values_list("timestamp", "count")[:20]
        )
        logger.warning(
            f"Found {duplicate_timestamp_count} duplicate-timestamp groups in deployment '{deployment}'. "
            f"Only one image will be used per timestamp for each event. First 20:\n{sample}"
        )

    image_timestamps = list(
        SourceImage.objects.filter(deployment=deployment)
        .exclude(timestamp=None)
        .values_list("timestamp", flat=True)
        .order_by("timestamp")
        .distinct()
    )

    timestamp_groups = ami.utils.dates.group_datetimes_by_gap(
        image_timestamps,
        max_time_gap,
        max_event_duration=max_event_duration,
    )

    events = []
    events_created_count = 0
    touched_event_pks: set[int] = set()
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
        event, was_created = Event.objects.get_or_create(
            deployment=deployment,
            group_by=group_by,
            defaults={"start": start_date, "end": end_date},
        )
        events.append(event)
        if was_created:
            events_created_count += 1
        touched_event_pks.add(event.pk)

        # Track events currently holding these captures — they'll lose captures
        # to the UPDATE below and need their cached fields refreshed at the end.
        touched_event_pks.update(
            SourceImage.objects.filter(deployment=deployment, timestamp__in=group)
            .exclude(event__isnull=True)
            .exclude(event=event)
            .values_list("event_id", flat=True)
            .distinct()
        )

        SourceImage.objects.filter(deployment=deployment, timestamp__in=group).update(event=event)
        event.save()  # Update start and end times and other cached fields
        logger.info(
            f"Created/updated event {event} with {len(group)} images for deployment {deployment}. "
            f"Duration: {event.duration_label()}"
        )

    logger.info(
        f"Done grouping {len(image_timestamps)} captures into {len(events)} events " f"for deployment {deployment}"
    )

    # Realign Occurrence.event_id with each occurrence's detections' current
    # source_image.event_id. Occurrences are bound to an event once at creation
    # time (Detection.associate_new_occurrence and Pipeline.save_results both
    # read source_image.event), and are never re-derived afterward. Without
    # this refresh, a deployment regrouped under the 24h cap keeps every
    # occurrence pointing at its original (pre-cap) event regardless of when
    # its detections actually fired — breaking every Occurrence.event-keyed
    # query (the occur_det_proj_evt index, Event.occurrences related-name,
    # event_ids= filters at models.py:4232-4477). Track the events currently
    # held by occurrences in this deployment before and after the refresh so
    # update_calculated_fields_for_events below picks up both losers and
    # gainers of occurrences when it recomputes occurrences_count.
    deployment_occurrences = Occurrence.objects.filter(deployment=deployment)
    touched_event_pks.update(
        deployment_occurrences.exclude(event__isnull=True).values_list("event_id", flat=True).distinct()
    )
    deployment_occurrences.update(
        event_id=models.Subquery(
            Detection.objects.filter(occurrence_id=models.OuterRef("pk"))
            .order_by("source_image__timestamp", "source_image_id", "pk")
            .values("source_image__event_id")[:1]
        )
    )
    touched_event_pks.update(
        deployment_occurrences.exclude(event__isnull=True).values_list("event_id", flat=True).distinct()
    )

    # Refresh cached fields on every event touched by grouping. An event reused
    # via matching group_by can lose captures to new events created by later
    # iterations above, leaving its start/end/captures_count stale — e.g. a
    # pre-existing multi-month event being re-grouped under a 24h cap.
    # (#904 is expected to rework this reuse path more thoroughly.)
    if touched_event_pks:
        update_calculated_fields_for_events(pks=list(touched_event_pks))

    events_deleted_empty = 0
    if delete_empty:
        logger.info("Deleting empty events for deployment")
        events_deleted_empty = delete_empty_events(deployment=deployment)

    for event in events:
        # Set the width and height of all images in each event based on the first image
        logger.info(f"Setting image dimensions for event {event}")
        set_dimensions_for_collection(event)

    # Refresh deployment-level cached counts. The async regroup_events task
    # never goes through Deployment.save's calculated-fields refresh, so
    # without this call the deployment list (occurrences_count, taxa_count,
    # etc.) keeps showing pre-regroup numbers until the next save touches it.
    # The save inside update_calculated_fields uses update_calculated_fields=False
    # so it doesn't re-enter the regroup path.
    logger.info("Updating cached fields on deployment")
    deployment.update_calculated_fields(save=True)

    audit_event_lengths(deployment)

    # Surface stats to the Jobs UI when this regroup is wrapped in a job.
    # "Ungrouped captures" = images with valid timestamps that didn't land in
    # any event (should be 0 unless an event delete races a capture insert;
    # useful signal). Param NAMES below are the human-readable labels shown
    # in the Jobs UI; stable retrieval keys are the slugify(name) forms (e.g.
    # "captures-grouped"). See REGROUP_STAGE_PARAM_NAMES in ami.jobs.models.
    if job and stage_key:
        ungrouped_captures_count = (
            SourceImage.objects.filter(deployment=deployment, event__isnull=True).exclude(timestamp=None).count()
        )
        no_timestamp_captures_count = SourceImage.objects.filter(deployment=deployment, timestamp=None).count()
        # Count actual SourceImage rows assigned to an event, not the count of
        # distinct timestamps in image_timestamps — two captures can share a
        # timestamp (duplicate_timestamp_count tracks this) and the UPDATE above
        # assigns both to the same event, so a distinct-timestamp count would
        # understate the work done.
        captures_grouped_count = (
            SourceImage.objects.filter(deployment=deployment, event__isnull=False).exclude(timestamp=None).count()
        )
        regroup_stats = {
            "Captures grouped": captures_grouped_count,
            "Events created": events_created_count,
            "Events touched": len(touched_event_pks),
            "Empty events deleted": events_deleted_empty,
            "Duplicate timestamps": duplicate_timestamp_count,
            "Ungrouped captures": ungrouped_captures_count,
            "Captures missing timestamp": no_timestamp_captures_count,
        }
        for param_name, value in regroup_stats.items():
            job.progress.add_or_update_stage_param(stage_key, param_name, value)
        job.update_progress()
        job.save()

    return events


def deployment_events_need_update(deployment: Deployment) -> bool:
    """
    Returns True if there are any SourceImages in the deployment
    that haven't been assigned to an `Event`.

    Note: This does not detect if images were deleted from the deployment
    after being grouped. We currently have limited support for image deletion,
    so handling that is out of scope for this check.
    """

    capture_counts_differ = deployment.captures_count != deployment.captures.count()

    ungrouped_images = models.Q(event__isnull=True)

    events_last_updated = (
        deployment.events.aggregate(
            latest_updated_at=models.Max("updated_at"),
        )["latest_updated_at"]
        or deployment.updated_at
        or datetime.datetime.min
    )
    images_updated_after_events = models.Q(updated_at__gt=events_last_updated)

    new_or_ungrouped_images = (
        SourceImage.objects.filter(deployment=deployment).filter(ungrouped_images | images_updated_after_events)
    ).exists()

    images_in_deployment_but_another_event = (
        SourceImage.objects.filter(deployment=deployment).exclude(event__deployment=deployment).exists()
    )

    needs_update = new_or_ungrouped_images or capture_counts_differ or images_in_deployment_but_another_event

    if needs_update:
        logger.info(
            f"Deployment {deployment} events need updating: "
            f"capture_counts_differ={capture_counts_differ}, "
            f"new_or_ungrouped_images={new_or_ungrouped_images}, "
            f"images_in_deployment_but_another_event={images_in_deployment_but_another_event}"
        )

    return needs_update


def delete_empty_events(deployment: Deployment, dry_run=False) -> int:
    """
    Delete events that have no images, occurrences or other related records.

    Returns the number of events deleted (or that would be deleted, for dry runs).
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

    count = events.count()
    if dry_run:
        for event in events:
            logger.debug(f"Would delete event {event} (dry run)")
    else:
        logger.info(f"Deleting {count} empty events")
        events.delete()
    return count


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


def validate_filename_timestamp(filename: str) -> None:
    # Ensure filename has a timestamp
    timestamp = ami.utils.dates.get_image_timestamp_from_filename(filename)
    if not timestamp:
        raise ValidationError("Image filename does not contain a valid timestamp (e.g. YYYYMMDDHHMMSS-snapshot.jpg).")


def create_source_image_from_upload(
    image: ImageFieldFile,
    deployment: Deployment,
    request=None,
    process_now=True,
) -> "SourceImage":
    """Create a complete SourceImage from an uploaded file."""

    # Read file content once
    image.seek(0)
    file_content = image.read()

    # Calculate a checksum for the image content
    checksum, checksum_algorithm = calculate_file_checksum(file_content)

    # Create PIL image from file content (no additional file reads)
    image_stream = BytesIO(file_content)
    pil_image = PIL.Image.open(image_stream)

    timestamp = extract_timestamp(filename=image.name, image=pil_image)
    if not timestamp:
        logger.warning(
            "A valid timestamp could not be found in the image's EXIF data or filename. "
            "Please rename the file to include a timestamp "
            "(e.g. YYYYMMDDHHMMSS-snapshot.jpg). "
            "Falling back to the current time for the image captured timestamp."
        )
        timestamp = timezone.now()
    width = pil_image.width
    height = pil_image.height
    size = len(file_content)

    # get full public media url of image:
    if request:
        base_url = request.build_absolute_uri(settings.MEDIA_URL)
    else:
        base_url = settings.MEDIA_URL

    source_image = SourceImage.objects.create(
        path=image.name,  # Includes relative path from MEDIA_ROOT
        public_base_url=base_url,  # @TODO how to merge this with the data source?
        project=deployment.project,
        deployment=deployment,
        timestamp=timestamp,
        event=None,  # Will be assigned when the image is grouped into events
        size=size,
        checksum=checksum,
        checksum_algorithm=checksum_algorithm,
        width=width,
        height=height,
        # The sync path stores the object's LastModified header here; set it on
        # upload too so source-vs-derivative freshness checks have a value.
        last_modified=timezone.now(),
        test_image=True,
        uploaded_by=request.user if request else None,
    )
    deployment.save(regroup_async=False)
    if process_now:
        from ami.ml.orchestration.processing import process_single_source_image

        process_single_source_image(source_image=source_image)
    return source_image


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


@final
class ClassificationResult(BaseModel):
    """A classification result from a model"""

    pass


class ClassificationQuerySet(BaseQuerySet):
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
    """A taxon classification of one detection: the taxon a classifier or a post-processing run assigned it.

    ``job`` records the run that wrote it, when there was one. ``algorithm_result`` is the
    post-processing result the row was created for, so the occurrence history can show a run
    with the classifications it produced; classifications from a pipeline leave it empty.
    """

    project_accessor = "detection__source_image__project"
    detection = models.ForeignKey(
        "Detection",
        on_delete=models.SET_NULL,
        null=True,
        related_name="classifications",
    )

    taxon = models.ForeignKey("Taxon", on_delete=models.SET_NULL, null=True, related_name="classifications")
    score = models.FloatField(null=True)
    timestamp = models.DateTimeField()  # Is this to represent when classification was made? why not use created_at?
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
    # The job that created this row. A later job that returns the same result reuses the row and
    # does not change it. Indexed by the partial index in Meta, not by the foreign key's own index.
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="classifications",
        db_index=False,
    )
    # Indexed by the partial index in Meta, not by the foreign key's own index.
    algorithm_result = models.ForeignKey(
        "ml.AlgorithmResult",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="classifications",
        db_index=False,
    )
    applied_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_classifications",
        help_text=(
            "If this classification was produced by a post-processing algorithm, "
            "this field references the original classification it was applied to."
        ),
    )
    objects = ClassificationManager()

    # Type hints for auto-generated fields
    taxon_id: int
    algorithm_id: int

    class Meta:
        ordering = ["-created_at", "-score"]
        indexes = [
            # Serves the ?job= occurrence filter with an index-only scan. Partial, because rows
            # written before jobs were recorded have no job. See #1471 for the measurements.
            models.Index(
                fields=["job", "detection"], name="cls_job_detection_idx", condition=models.Q(job__isnull=False)
            ),
            # Deleting a result looks up its classifications. Partial, because pipeline
            # classifications never have a result.
            models.Index(
                fields=["algorithm_result"],
                name="cls_algorithm_result_idx",
                condition=models.Q(algorithm_result__isnull=False),
            ),
        ]

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
            logger.warning(
                f"Classification {self.pk}'s algorithm ({self.algorithm_id}) has no category map, "
                "can't get top N predictions."
            )
            return []

        top_scored = self.top_scores_with_index(n)  # (index, score) pairs
        indexes = [idx for idx, _ in top_scored]
        category_data: list[dict] = self.category_map.with_taxa(only_indexes=indexes)
        assert category_data is not None
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


class DetectionQuerySet(BaseQuerySet):
    def valid(self):
        """
        Detections suitable for consumer queries — excludes null-marker sentinels.

        Null markers are rows that record "an algorithm ran against this image and
        found nothing." Consumers asking "give me detections" should always go
        through .valid(). Future predicates to fold in here: soft-delete tombstones,
        detections missing an algorithm reference, detections missing classifications.
        """
        return self.exclude(NULL_DETECTIONS_FILTER)

    def null_markers(self):
        """
        Sentinel rows that record "this algorithm ran against this image and found
        nothing." Only relevant for SourceImage-level "has this been processed?"
        questions. Detection consumers should use .valid() instead.
        """
        return self.filter(NULL_DETECTIONS_FILTER)


class DetectionManager(models.Manager.from_queryset(DetectionQuerySet)):
    pass


@final
class Detection(BaseModel):
    """An object detected in an image"""

    project_accessor = "source_image__project"
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
    # The job that created this row. A later job that returns the same box reuses the row and
    # does not change it. Indexed by the partial index in Meta, not by the foreign key's own index.
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="detections",
        db_index=False,
    )

    similarity_vector = models.JSONField(null=True, blank=True)

    # For type hints
    classifications: models.QuerySet["Classification"]
    source_image_id: int
    detection_algorithm_id: int

    objects = DetectionManager()

    NULL_BBOX = None
    """Canonical bbox value for null markers (rows that record 'an algorithm ran but
    found nothing'). Null markers are stored as SQL NULL; use Detection.build_null_marker()
    to construct them."""

    @property
    def is_null_marker(self) -> bool:
        """True for sentinel rows representing 'no detections found by this algorithm.'"""
        return self.bbox is None

    @classmethod
    def build_null_marker(cls, source_image, detection_algorithm) -> "Detection":
        """Construct (without saving) a null-marker Detection for the given image+algorithm."""
        return cls(
            source_image=source_image,
            bbox=cls.NULL_BBOX,
            detection_algorithm=detection_algorithm,
        )

    def get_bbox(self):
        if self.bbox:
            return BoundingBox(
                x1=self.bbox[0],
                y1=self.bbox[1],
                x2=self.bbox[2],
                y2=self.bbox[3],
            )
        else:
            return None

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

    def width(self) -> float | None:
        """Placeholder for queryset annotation. Use BoundingBox.from_coords() for bbox validation."""
        return None

    def height(self) -> float | None:
        """Placeholder for queryset annotation. Use BoundingBox.from_coords() for bbox validation."""
        return None

    class Meta:
        ordering = [
            "frame_num",
            "timestamp",
        ]
        indexes = [
            # Supports the "last processed" subquery on the captures list: the
            # latest detection created_at per source image (index scan, top 1).
            models.Index(fields=["source_image", "-created_at"], name="det_srcimg_created_idx"),
            # Serves the ?job= occurrence filter with an index-only scan. Partial, because rows
            # written before jobs were recorded have no job. See #1471 for the measurements.
            models.Index(
                fields=["job", "occurrence"], name="det_job_occurrence_idx", condition=models.Q(job__isnull=False)
            ),
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

    def occurrence_meets_criteria(self) -> bool | None:
        """
        This is added an annotated field, it should not be called directly.

        If the value is None, it means it has not been annotated and not calculated.
        In that case, no detections should be returned in the API.
        """
        return None

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
