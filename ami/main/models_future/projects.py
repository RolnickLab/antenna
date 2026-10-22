"""
The Project model and related classes and functions.
"""

import logging
from typing import TYPE_CHECKING, Final, final

import pydantic
from django.contrib.auth.models import AnonymousUser
from django.db import models, transaction
from django.db.models import OuterRef, Subquery
from django.db.models.functions import Coalesce
from django_pydantic_field import SchemaField

from ami.base.models import BaseModel, BaseQuerySet
from ami.main import charts
from ami.users.models import User

if TYPE_CHECKING:
    from ami.jobs.models import Job
    from ami.main.models import Deployment, Device, Event, Occurrence, Site, SourceImage, SourceImageCollection
    from ami.main.models_future.taxonomy import Tag, TaxaList, Taxon
    from ami.ml.models import Pipeline, ProcessingService

logger = logging.getLogger(__name__)

_POST_TITLE_MAX_LENGTH: Final = 80


class ProjectSettingsMixin(models.Model):
    """
    User definable settings for projects.

    This is a mixin that will be flattened out into the final model.
    It allows us to organize user-defined project settings in their own class
    without needing to create a separate model.
    """

    default_processing_pipeline = models.ForeignKey(
        "ml.Pipeline",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_projects",
        help_text=(
            "The default pipeline to use for processing images in this project. "
            "This is used to determine which processing service to run on new images. "
            # "Use the global unique key of the Pipeline, which may be a slug or a UUID. "
            # "Cannot be a Pipeline instance yet, because the Pipelines have likely not been created yet."
        ),
    )

    session_time_gap_seconds = models.IntegerField(
        default=60 * 60 * 2,  # Default to 2 hours
        help_text=(
            "Maximum gap between consecutive captures (in seconds) before a new session is started. "
            "Changing this value does not regroup existing captures automatically — to apply, "
            "select the affected deployments on the Deployments admin page and run the "
            '"Regroup captures into sessions" action.'
        ),
    )

    default_filters_score_threshold = models.FloatField(
        default=0.5,
        help_text="Default score threshold for filtering occurrences",
    )

    default_filters_include_taxa = models.ManyToManyField(
        "Taxon",
        related_name="include_taxa_default_projects",
        blank=True,
        help_text=(
            "Taxa that are included by default in the occurrence filters and metrics. "
            "For example, the top-level taxa like 'Moths' or 'Arthropods'. "
        ),
    )

    default_filters_exclude_taxa = models.ManyToManyField(
        "Taxon",
        related_name="exclude_taxa_default_projects",
        blank=True,
        help_text=(
            "Taxa that are excluded by default in the occurrence filters and metrics. " "For example, 'Not a Moth'."
        ),
    )

    # settings_updated_at = models.DateTimeField(auto_now=True, help_text="Last time any setting was updated")

    class Meta:
        # Do not create a separate table for this mixin
        abstract = True

    @classmethod
    def get_settings_field_names(cls) -> list[str]:
        """
        Automatically discover settings fields by comparing with BaseModel.

        This finds fields that exist in the final model but not in BaseModel,
        which means they were added by this mixin.
        """
        from ami.base.models import BaseModel  # Adjust import as needed

        # Get all field names from the final model
        all_fields = {f.name for f in cls._meta.get_fields()}

        # Get all field names from BaseModel
        base_fields = {f.name for f in BaseModel._meta.get_fields()}

        # Settings fields are those not in BaseModel
        settings_fields = all_fields - base_fields

        # Filter out reverse relations and other auto-generated fields
        real_settings_fields = []
        for field_name in settings_fields:
            try:
                field = cls._meta.get_field(field_name)
                # Skip auto-created fields and foreign key ID fields
                if not (field.auto_created or field.name.endswith("_id")):
                    real_settings_fields.append(field_name)
            except Exception:
                # Skip fields that can't be retrieved (like reverse relations)
                continue

        return sorted(real_settings_fields)


def _per_project(queryset: models.QuerySet, aggregate) -> Subquery:
    """One aggregate over the rows of `queryset` that belong to the outer project, for a Project annotation."""
    return Subquery(
        queryset.filter(project=OuterRef("pk"))
        .order_by()
        .values("project")
        .annotate(value=aggregate)
        .values("value")[:1]
    )


class ProjectQuerySet(BaseQuerySet):
    # Annotated by with_overview_counts() and with_recent_activity(). The projects API sorts and
    # serializes by these names.
    OVERVIEW_COUNT_FIELDS = ("deployments_count", "captures_count", "occurrences_count", "members_count")
    RECENT_ACTIVITY_FIELDS = ("last_capture_timestamp", "last_occurrence_updated_at", "last_job_updated_at")
    # Annotated by with_location().
    LOCATION_FIELDS = ("centroid_latitude", "centroid_longitude")

    def filter_by_user(self, user: User):
        """
        Filters projects to include only those where the given user is a member.
        """
        return self.filter(members=user)

    def with_overview_counts(self, user: User | AnonymousUser) -> "ProjectQuerySet":
        """
        Annotate the totals shown in the projects table, named in OVERVIEW_COUNT_FIELDS.

        Totals are summed from the cached counts on each deployment, so they are only as fresh as
        `Deployment.update_calculated_fields()`. `members_count` is null on projects whose team list
        the user may not open, the same check as `UserProjectMembership.check_permission()`.
        """
        from guardian.shortcuts import get_objects_for_user

        from ami.main.models import Deployment, UserProjectMembership

        can_view_team = get_objects_for_user(
            user,
            Project.Permissions.VIEW_USER_PROJECT_MEMBERSHIP,
            klass=Project,
            accept_global_perms=False,
        )
        members_count = models.Case(
            models.When(
                pk__in=can_view_team.values("pk"),
                then=Coalesce(_per_project(UserProjectMembership.objects.all(), models.Count("pk")), 0),
            ),
            default=None,
        )

        return self.annotate(
            deployments_count=Coalesce(_per_project(Deployment.objects.all(), models.Count("pk")), 0),
            captures_count=Coalesce(_per_project(Deployment.objects.all(), models.Sum("captures_count")), 0),
            occurrences_count=Coalesce(_per_project(Deployment.objects.all(), models.Sum("occurrences_count")), 0),
            members_count=members_count,
        )

    def with_recent_activity(self) -> "ProjectQuerySet":
        """
        Annotate when each project last received a capture, an occurrence update and a job update,
        named in RECENT_ACTIVITY_FIELDS. Each is read live from a (project, time) index.
        """
        from ami.jobs.models import Job
        from ami.main.models import Occurrence, SourceImage

        def latest(queryset: models.QuerySet, field: str) -> Subquery:
            return Subquery(queryset.filter(project=OuterRef("pk")).order_by(f"-{field}").values(field)[:1])

        return self.annotate(
            # timestamp is nullable and DESC sorts NULLs first, so undated captures are excluded.
            last_capture_timestamp=latest(SourceImage.objects.filter(timestamp__isnull=False), "timestamp"),
            last_occurrence_updated_at=latest(Occurrence.objects.all(), "updated_at"),
            last_job_updated_at=latest(Job.objects.all(), "updated_at"),
        )

    def with_location(self) -> "ProjectQuerySet":
        """
        Annotate LOCATION_FIELDS: the centroid of the project's stations, as the mean of their coordinates.

        Stations without coordinates, or at (0, 0) where default stations are created, are left
        out; a project with none of its own gets nulls. A plain mean is wrong for stations on
        both sides of the antimeridian.
        """
        from ami.main.models import Deployment

        located = Deployment.objects.filter(latitude__isnull=False, longitude__isnull=False).exclude(
            latitude=0, longitude=0
        )
        return self.annotate(
            centroid_latitude=_per_project(located, models.Avg("latitude")),
            centroid_longitude=_per_project(located, models.Avg("longitude")),
        )


class ProjectManager(models.Manager.from_queryset(ProjectQuerySet)):
    pass

    def create(self, create_defaults: bool = True, **kwargs) -> "Project":
        """
        Create a new Project and related models with defaults.

        Args:
            create_defaults: Whether to create default related models
            **kwargs: Model field values

        Returns:
            Created Project instance
        """
        with transaction.atomic():
            project_instance = super().create(**kwargs)
            logger.info(f"Created project: {project_instance.name}")

            if create_defaults:
                self.create_related_defaults(project_instance)

            return project_instance

    def create_related_defaults(self, project: "Project"):
        """Create default device, and other related models for this project if they don't exist."""
        from ami.main.models import (
            get_or_create_default_collection,
            get_or_create_default_deployment,
            get_or_create_default_device,
            get_or_create_default_research_site,
        )

        device = get_or_create_default_device(project=project)
        site = get_or_create_default_research_site(project=project)
        if not project.deployments.exists():
            get_or_create_default_deployment(project=project, site=site, device=device)
        if not project.sourceimage_collections.exists():
            get_or_create_default_collection(project=project)
        if not project.processing_services.exists():
            from ami.ml.models.processing_service import get_or_create_default_processing_service

            get_or_create_default_processing_service(project=project)


class ProjectFeatureFlags(pydantic.BaseModel):
    """
    Feature flags for the project.
    """

    tags: bool = False  # Whether the project supports tagging taxa
    reprocess_existing_detections: bool = False  # Whether to reprocess existing detections
    default_filters: bool = False  # Whether to show default filters form in UI
    # Feature flag for jobs to reprocess all images in the project, even if already processed
    reprocess_all_images: bool = False
    async_pipeline_workers: bool = True  # Whether to use async pipeline workers that pull tasks from a queue


def get_default_feature_flags() -> ProjectFeatureFlags:
    return ProjectFeatureFlags()


@final
class Project(ProjectSettingsMixin, BaseModel):
    """ """

    name = models.CharField(max_length=_POST_TITLE_MAX_LENGTH)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="projects", blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="projects")
    members = models.ManyToManyField(
        User,
        through="UserProjectMembership",
        related_name="user_projects",
        blank=True,
    )
    draft = models.BooleanField(
        default=False,
        help_text="Indicates whether this project is in draft mode",
    )
    feature_flags = SchemaField(
        ProjectFeatureFlags,
        default=get_default_feature_flags,
        null=False,
        blank=True,
    )

    active = models.BooleanField(default=True)
    priority = models.IntegerField(default=1)

    # Backreferences for type hinting
    captures: models.QuerySet["SourceImage"]
    deployments: models.QuerySet["Deployment"]
    events: models.QuerySet["Event"]
    occurrences: models.QuerySet["Occurrence"]
    taxa: models.QuerySet["Taxon"]
    taxa_lists: models.QuerySet["TaxaList"]
    devices: models.QuerySet["Device"]
    sites: models.QuerySet["Site"]
    jobs: models.QuerySet["Job"]
    sourceimage_collections: models.QuerySet["SourceImageCollection"]
    processing_services: models.QuerySet["ProcessingService"]
    pipelines: models.QuerySet["Pipeline"]
    tags: models.QuerySet["Tag"]

    objects = ProjectManager()

    def ensure_owner_membership(self):
        """Add owner to members if they are not already a member"""
        if self.owner and not self.members.filter(id=self.owner.pk).exists():
            self.members.add(self.owner)

    @property
    def thumbnails_enabled(self) -> bool:
        """Whether captures in this project should expose server-generated thumbnail URLs.

        Draft projects aren't anonymously readable, and the thumbnail endpoint is loaded
        via an anonymous <img> tag that can't authenticate, so it would 401. Proxy for
        "anonymous can retrieve captures"; revisit if visibility decouples from `draft`.
        Serving thumbnails for private projects is tracked in #1341.
        """
        return not self.draft

    def deployments_count(self) -> int:
        return self.deployments.count()

    def taxa_count(self):
        return self.taxa.all().count()

    def summary_data(self):
        """
        Data prepared for rendering charts with plotly.js on the overview page.
        """

        return [
            {
                "id": "captures",
                "title": "Captures",
                "plots": [
                    charts.captures_per_hour(project_pk=self.pk),
                    charts.captures_per_month(project_pk=self.pk),
                ],
            },
            {
                "id": "occurrences",
                "title": "Occurrences",
                "plots": [
                    charts.detections_per_hour(project_pk=self.pk),
                    charts.average_occurrences_per_month(project_pk=self.pk),
                ],
            },
            {
                "id": "taxa",
                "title": "Taxa",
                "plots": [
                    charts.project_top_taxa(project_pk=self.pk),
                    charts.unique_species_per_month(project_pk=self.pk),
                ],
            },
        ]

    def update_related_calculated_fields(self):
        """
        Update calculated fields for all related events, deployments, and source images.
        """
        from ami.main.models import SourceImage, update_detection_counts

        # Update events
        for event in self.events.all():
            event.update_calculated_fields(save=True)

        # Update deployments
        for deployment in self.deployments.all():
            deployment.update_calculated_fields(save=True)

        # Update source image cached detection counts using the project's default filters
        # so SourceImage.detections_count stays consistent with get_detections_count().
        update_detection_counts(qs=SourceImage.objects.filter(project=self), project=self)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Add owner to members
        self.ensure_owner_membership()

    def check_custom_permission(self, user, action: str) -> bool:
        """
        Check custom permissions for actions like 'charts'.
        Charts is treated as a read-only operation, so it follows the same
        permission logic as 'retrieve'.
        """
        from ami.users.roles import BasicMember, ProjectManager

        if action == "charts":
            # Same permission logic as retrieve action
            if self.draft:
                # Allow view permission for members and owners of draft projects
                return BasicMember.has_role(user, self) or user == self.owner or user.is_superuser
            return True

        if action == "pipelines":
            # Pipeline registration requires project management permissions
            return ProjectManager.has_role(user, self) or user == self.owner or user.is_superuser

        # Fall back to default permission checking for other actions
        return super().check_custom_permission(user, action)

    class Permissions:
        """CRUD Permission names follow the convention: `create_<model>`, `update_<model>`,
        `delete_<model>`, `view_<model>`"""

        # Project permissions
        VIEW_PROJECT = "view_project"
        UPDATE_PROJECT = "update_project"
        DELETE_PROJECT = "delete_project"
        CREATE_PROJECT = "create_project"

        # Identification permissions
        CREATE_IDENTIFICATION = "create_identification"
        UPDATE_IDENTIFICATION = "update_identification"
        DELETE_IDENTIFICATION = "delete_identification"

        # Job permissions
        CREATE_JOB = "create_job"
        UPDATE_JOB = "update_job"
        RUN_ML_JOB = "run_ml_job"
        RUN_SINGLE_IMAGE_JOB = "run_single_image_ml_job"
        RUN_POPULATE_CAPTURES_COLLECTION_JOB = "run_populate_captures_collection_job"
        RUN_DATA_STORAGE_SYNC_JOB = "run_data_storage_sync_job"
        RUN_REGROUP_EVENTS_JOB = "run_regroup_events_job"
        RUN_DATA_EXPORT_JOB = "run_data_export_job"
        RUN_POST_PROCESSING_JOB = "run_post_processing_job"
        DELETE_JOB = "delete_job"

        # Deployment permissions
        CREATE_DEPLOYMENT = "create_deployment"
        DELETE_DEPLOYMENT = "delete_deployment"
        UPDATE_DEPLOYMENT = "update_deployment"
        SYNC_DEPLOYMENT = "sync_deployment"
        REGROUP_SESSIONS_DEPLOYMENT = "regroup_sessions_deployment"

        # Collection permissions
        CREATE_COLLECTION = "create_sourceimagecollection"
        UPDATE_COLLECTION = "update_sourceimagecollection"
        DELETE_COLLECTION = "delete_sourceimagecollection"
        POPULATE_COLLECTION = "populate_sourceimagecollection"

        # Source Image permissions
        CREATE_SOURCE_IMAGE = "create_sourceimage"
        UPDATE_SOURCE_IMAGE = "update_sourceimage"
        DELETE_SOURCE_IMAGE = "delete_sourceimage"
        STAR_SOURCE_IMAGE = "star_sourceimage"

        # SourceImageUpload permissions
        CREATE_SOURCE_IMAGE_UPLOAD = "create_sourceimageupload"
        UPDATE_SOURCE_IMAGE_UPLOAD = "update_sourceimageupload"
        DELETE_SOURCE_IMAGE_UPLOAD = "delete_sourceimageupload"
        # Storage permissions
        CREATE_STORAGE = "create_s3storagesource"
        DELETE_STORAGE = "delete_s3storagesource"
        UPDATE_STORAGE = "update_s3storagesource"
        TEST_STORAGE = "test_s3storagesource"

        # Site permissions
        CREATE_SITE = "create_site"
        DELETE_SITE = "delete_site"
        UPDATE_SITE = "update_site"

        # Device permissions
        CREATE_DEVICE = "create_device"
        DELETE_DEVICE = "delete_device"
        UPDATE_DEVICE = "update_device"
        # User project membership permissions
        VIEW_USER_PROJECT_MEMBERSHIP = "view_userprojectmembership"
        CREATE_USER_PROJECT_MEMBERSHIP = "create_userprojectmembership"
        UPDATE_USER_PROJECT_MEMBERSHIP = "update_userprojectmembership"
        DELETE_USER_PROJECT_MEMBERSHIP = "delete_userprojectmembership"

        # Data Export permissions
        CREATE_DATA_EXPORT = "create_dataexport"
        UPDATE_DATA_EXPORT = "update_dataexport"
        DELETE_DATA_EXPORT = "delete_dataexport"

        # Pipeline configuration permissions
        CREATE_PROJECT_PIPELINE_CONFIG = "create_projectpipelineconfig"
        UPDATE_PROJECT_PIPELINE_CONFIG = "update_projectpipelineconfig"
        DELETE_PROJECT_PIPELINE_CONFIG = "delete_projectpipelineconfig"

        # TaxaList permissions
        CREATE_TAXALIST = "create_taxalist"
        UPDATE_TAXALIST = "update_taxalist"
        DELETE_TAXALIST = "delete_taxalist"

        # Other permissions
        VIEW_PRIVATE_DATA = "view_private_data"
        DELETE_OCCURRENCES = "delete_occurrences"
        IMPORT_DATA = "import_data"

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
            ("run_ml_job", "Can run/retry/cancel ML jobs"),
            ("run_populate_captures_collection_job", "Can run/retry/cancel Populate Collection jobs"),
            ("run_data_storage_sync_job", "Can run/retry/cancel Data Storage Sync jobs"),
            ("run_regroup_events_job", "Can run/retry/cancel Regroup Events jobs"),
            ("run_data_export_job", "Can run/retry/cancel Data Export jobs"),
            ("run_single_image_ml_job", "Can process a single capture"),
            ("run_post_processing_job", "Can run/retry/cancel Post-Processing jobs"),
            ("delete_job", "Can delete a job"),
            # Deployment permissions
            ("create_deployment", "Can create a deployment"),
            ("delete_deployment", "Can delete a deployment"),
            ("update_deployment", "Can update a deployment"),
            ("sync_deployment", "Can sync images to a deployment"),
            ("regroup_sessions_deployment", "Can regroup deployment captures into sessions"),
            # Collection permissions
            ("create_sourceimagecollection", "Can create a collection"),
            ("update_sourceimagecollection", "Can update a collection"),
            ("delete_sourceimagecollection", "Can delete a collection"),
            ("populate_sourceimagecollection", "Can populate a collection"),
            # Source Image permissions
            ("create_sourceimage", "Can create a source image"),
            ("update_sourceimage", "Can update a source image"),
            ("delete_sourceimage", "Can delete a source image"),
            ("star_sourceimage", "Can star a source image"),
            # SourceImageUpload permissions
            ("create_sourceimageupload", "Can create a source image upload"),
            ("update_sourceimageupload", "Can update a source image upload"),
            ("delete_sourceimageupload", "Can delete a source image upload"),
            # Storage permissions
            ("create_s3storagesource", "Can create storage"),
            ("delete_s3storagesource", "Can delete storage"),
            ("update_s3storagesource", "Can update storage"),
            ("test_s3storagesource", "Can test storage connection"),
            # Site permissions
            ("create_site", "Can create a site"),
            ("delete_site", "Can delete a site"),
            ("update_site", "Can update a site"),
            # Device permissions
            ("create_device", "Can create a device"),
            ("delete_device", "Can delete a device"),
            ("update_device", "Can update a device"),
            # User project membership permissions
            ("view_userprojectmembership", "Can view project members"),
            ("create_userprojectmembership", "Can add a user to the project"),
            ("update_userprojectmembership", "Can update a user's project membership and role in the project"),
            ("delete_userprojectmembership", "Can remove a user from the project"),
            # Data Export permissions
            ("create_dataexport", "Can create a data export"),
            ("update_dataexport", "Can update a data export"),
            ("delete_dataexport", "Can delete a data export"),
            # Pipeline configuration permissions
            ("create_projectpipelineconfig", "Can register pipelines for the project"),
            ("update_projectpipelineconfig", "Can update pipeline configurations"),
            ("delete_projectpipelineconfig", "Can remove pipelines from the project"),
            # TaxaList permissions
            ("create_taxalist", "Can create a taxa list"),
            ("update_taxalist", "Can update a taxa list"),
            ("delete_taxalist", "Can delete a taxa list"),
            # Other permissions
            ("view_private_data", "Can view private data"),
        ]
