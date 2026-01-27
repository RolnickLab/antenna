from typing import Any

from django.contrib import admin
from django.db import models
from django.db.models.query import QuerySet
from django.http.request import HttpRequest
from django.template.defaultfilters import filesizeformat
from django.utils.formats import number_format
from guardian.admin import GuardedModelAdmin

import ami.utils
from ami import tasks
from ami.jobs.models import Job
from ami.ml.models.project_pipeline_config import ProjectPipelineConfig
from ami.ml.tasks import remove_duplicate_classifications

from .models import (
    BlogPost,
    Classification,
    Deployment,
    Detection,
    Device,
    Event,
    Occurrence,
    Project,
    S3StorageSource,
    Site,
    SourceImage,
    SourceImageCollection,
    Tag,
    TaxaList,
    Taxon,
)


class ProjectPipelineConfigInline(admin.TabularInline):
    model = ProjectPipelineConfig
    extra = 0


class AdminBase(admin.ModelAdmin):
    """Mixin to add ``created_at`` and ``updated_at`` to admin panel."""

    readonly_fields = ("created_at", "updated_at")

    @admin.action(description="Save selected instances in the background")
    def save_async(self, request: HttpRequest, queryset: QuerySet[SourceImage]) -> None:
        app_label = self.model._meta.app_label
        model_name = self.model._meta.model_name
        assert app_label and model_name, "Model must have app_label and model_name"
        batch_size = 10
        # @TODO should these IDs be split into chunks here for millions of records?
        # Can we use a queryset iterator or send the queryset directly to the task?
        instance_pks = list(queryset.values_list("pk", flat=True))
        tasks.save_model_instances(app_label=app_label, model_name=model_name, pks=instance_pks, batch_size=100)
        self.message_user(request, f"Saving {len(instance_pks)} instances in background in batches of {batch_size}.")

    actions = [save_async]


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin[BlogPost]):
    """Admin panel example for ``BlogPost`` model."""


@admin.register(Project)
class ProjectAdmin(GuardedModelAdmin):
    """Admin panel for ``Project`` model."""

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.ensure_owner_membership()

    list_display = ("name", "owner", "priority", "active", "created_at", "updated_at")
    list_filter = ("active", "owner")
    search_fields = ("name", "owner__email")

    inlines = [ProjectPipelineConfigInline]
    autocomplete_fields = ("default_filters_include_taxa", "default_filters_exclude_taxa")

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "description",
                    "priority",
                    "active",
                    "draft",
                    "feature_flags",
                )
            },
        ),
        (
            "Settings",
            {
                "fields": (
                    "default_processing_pipeline",
                    "session_time_gap_seconds",
                    "default_filters_score_threshold",
                    "default_filters_include_taxa",
                    "default_filters_exclude_taxa",
                ),
            },
        ),
        (
            "Ownership & Access",
            {
                "fields": ("owner",),
                "classes": ("wide",),
            },
        ),
    )

    @admin.action(description="Remove duplicate classifications from all detections")
    def _remove_duplicate_classifications(self, request: HttpRequest, queryset: QuerySet[Project]) -> None:
        task_ids = []
        for project in queryset:
            task = remove_duplicate_classifications.delay(project_id=project.pk)
            task_ids.append(task.id)
        self.message_user(request, f"Started {len(task_ids)} tasks to delete classification: {task_ids}")

    actions = [_remove_duplicate_classifications]


@admin.register(Deployment)
class DeploymentAdmin(admin.ModelAdmin[Deployment]):
    """Admin panel example for ``Deployment`` model."""

    list_display = (
        "name",
        "project",
        "data_source_uri",
        "captures_count",
        "captures_size",
        "events_count",
        "start_date",
        "end_date",
    )

    search_fields = (
        "id",
        "name",
    )

    def start_date(self, obj) -> str | None:
        result = SourceImage.objects.filter(event__deployment=obj).aggregate(
            models.Min("timestamp"),
        )
        return result["timestamp__min"].date() if result["timestamp__min"] else None

    def end_date(self, obj) -> str | None:
        result = SourceImage.objects.filter(deployment=obj).aggregate(
            models.Max("timestamp"),
        )
        return result["timestamp__max"].date() if result["timestamp__max"] else None

    def events_count(self, obj) -> str | None:
        return number_format(obj.events.count(), force_grouping=True, use_l10n=True)

    def captures_size(self, obj) -> str | None:
        return filesizeformat(obj.data_source_total_size)

    def captures_count(self, obj) -> str | None:
        total_files = obj.data_source_total_files
        return number_format(total_files, force_grouping=True, use_l10n=True)

    # list action that runs deployment.import_captures and displays a message
    # https://docs.djangoproject.com/en/3.2/ref/contrib/admin/actions/#writing-action-functions
    @admin.action(description="Sync captures from deployment's data source (async)")
    def sync_captures(self, request: HttpRequest, queryset: QuerySet[Deployment]) -> None:
        queued_tasks = [tasks.sync_source_images.delay(deployment.pk) for deployment in queryset]
        msg = f"Syncing captures for {len(queued_tasks)} deployments in background: {queued_tasks}"
        self.message_user(request, msg)

    # Action that regroups all captures in the deployment into events
    @admin.action(description="Regroup captures into events (async)")
    def regroup_events(self, request: HttpRequest, queryset: QuerySet[Deployment]) -> None:
        queued_tasks = [tasks.regroup_events.delay(deployment.pk) for deployment in queryset]
        msg = f"Regrouping captures into events for {len(queued_tasks)} deployments in background: {queued_tasks}"
        self.message_user(request, msg)

    list_filter = ("project",)
    actions = [sync_captures, regroup_events]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        qs = super().get_queryset(request)
        # Use select_related to avoid extra queries when displaying related fields
        qs = qs.select_related("project", "data_source")
        # Annotate queryset with capture counts
        # qs = qs.annotate(captures_count=Count("captures"))
        # qs = qs.annotate(captures_size=Sum("captures__size"))
        return qs


@admin.register(Event)
class EventAdmin(admin.ModelAdmin[Event]):
    """Admin panel example for ``Event`` model."""

    list_display = (
        "name",
        "deployment",
        "start",
        "duration_display",
        "captures_count",
        "project",
        "updated_at",
        "calculated_fields_updated_at",
    )

    readonly_fields = (
        "captures_count",
        "detections_count",
        "occurrences_count",
        "calculated_fields_updated_at",
    )

    search_fields = (
        "id",
        "name",
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        qs = super().get_queryset(request)
        from django.db.models import ExpressionWrapper, F
        from django.db.models.fields import DurationField

        return qs.select_related("deployment", "project").annotate(
            time_duration=ExpressionWrapper(F("end") - F("start"), output_field=DurationField()),
        )

    @admin.display(
        description="Duration",
        ordering="time_duration",
    )
    def duration_display(self, obj) -> str:
        return ami.utils.dates.format_timedelta(obj.time_duration)

    # Save all events in queryset
    @admin.action(description="Updated pre-calculated fields")
    def update_calculated_fields(self, request: HttpRequest, queryset: QuerySet[Event]) -> None:
        from ami.main.models import update_calculated_fields_for_events

        update_calculated_fields_for_events(qs=queryset)
        self.message_user(request, f"Updated {queryset.count()} events.")

    list_filter = ("deployment", "project", "start")
    actions = [update_calculated_fields]


@admin.register(SourceImage)
class SourceImageAdmin(AdminBase):
    """Admin panel example for ``SourceImage`` model."""

    list_display = (
        "path",
        "timestamp",
        "event",
        "detections_count",
        "deployment",
        "width",
        "height",
        "size",
        "checksum",
        "checksum_algorithm",
        "created_at",
    )

    list_filter = (
        "deployment__project",
        "deployment",
        "timestamp",
        "deployment__data_source",
        "collections",
    )

    search_fields = (
        "id",
        "path",
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).select_related("event", "deployment", "deployment__data_source")


class ClassificationInline(admin.TabularInline):
    model = Classification
    extra = 0
    fields = (
        "taxon",
        "algorithm",
        "timestamp",
        "terminal",
        "created_at",
    )
    readonly_fields = (
        "taxon",
        "algorithm",
        "timestamp",
        "terminal",
        "created_at",
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        qs = super().get_queryset(request)
        return qs.select_related("taxon", "algorithm", "detection")


class DetectionInline(admin.TabularInline):
    model = Detection
    extra = 0
    fields = (
        "detection_algorithm",
        "source_image",
        "timestamp",
        "created_at",
        "occurrence",
    )
    readonly_fields = (
        "detection_algorithm",
        "source_image",
        "timestamp",
        "created_at",
        "occurrence",
    )


@admin.register(Detection)
class DetectionAdmin(admin.ModelAdmin[Detection]):
    """Admin panel example for ``Detection`` model."""

    list_display = (
        "id",
        "source_image",
        "timestamp",
        "occurrence",
        "classifications_count",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = ("source_image", "occurrence")

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        qs = super().get_queryset(request)
        return qs.select_related("source_image", "occurrence").annotate(
            classifications_count=models.Count("classifications"),
        )

    @admin.display(
        description="Classifications",
        ordering="classifications_count",
    )
    def classifications_count(self, obj) -> int:
        return obj.classifications_count

    ordering = ("-created_at",)

    inlines = [ClassificationInline]


@admin.register(Occurrence)
class OccurrenceAdmin(admin.ModelAdmin[Occurrence]):
    """Admin panel example for ``Occurrence`` model."""

    list_display = (
        "id",
        "determination",
        "project",
        "deployment",
        "event",
        "detections_count",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = ("determination", "project", "deployment", "event")
    list_filter = (
        "project",
        "deployment",
        "determination__rank",
        "created_at",
    )
    search_fields = ("determination__name", "determination__search_names")

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        qs = super().get_queryset(request)
        qs = qs.select_related("determination", "project", "deployment", "event")
        # Add detections count to queryset
        qs = qs.annotate(detections_count=models.Count("detections"))
        # Add min, max and avg detection__classifications counts to queryset
        # qs = qs.annotate(
        #     min_detection_classifications=models.Min("detections__classifications"),
        #     max_detection_classifications=models.Max("detections__classifications"),
        #     avg_detection_classifications=models.Avg("detections__classifications"),
        # )
        return qs

    @admin.display(
        description="Detections",
        ordering="detections_count",
    )
    def detections_count(self, obj) -> int:
        return obj.detections_count

    ordering = ("-created_at",)

    # Add classifications as inline
    inlines = [DetectionInline]


@admin.register(Classification)
class ClassificationAdmin(admin.ModelAdmin[Classification]):
    list_display = (
        "__str__",
        "taxon",
        "algorithm",
        "num_scores",
        "num_logits",
        "detection_date",
        "timestamp",
        "terminal",
        "created_at",
    )

    list_filter = (
        "algorithm",
        "terminal",
        "created_at",
        "detection__source_image__project",
        "taxon__rank",
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        qs = super().get_queryset(request)
        return qs.select_related(
            "taxon", "detection", "detection__source_image", "detection__source_image__project"
        ).annotate(
            detection_date=models.F("detection__timestamp"),
        )

    @admin.display()
    def detection_date(self, obj: Classification) -> str:
        # This property comes from the annotation in get_queryset, not the model
        return obj.detection_date  # type: ignore

    def num_scores(self, obj: Classification) -> int:
        return len(obj.scores) if obj.scores else 0

    def num_logits(self, obj: Classification) -> int:
        return len(obj.logits) if obj.logits else 0


class TaxonParentFilter(admin.SimpleListFilter):
    """
    Return all taxa that are not species.
    """

    title = "Taxon parent"
    parameter_name = "parent"

    def lookups(self, request, model_admin):
        # return Taxon.objects.exclude(rank="SPECIES").values_list("id", "name")
        choices = [(taxon.pk, str(taxon)) for taxon in Taxon.objects.exclude(rank__in=["SPECIES", "GENUS", "UNKNOWN"])]
        return choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(parent__id=self.value())
        return queryset


@admin.register(Taxon)
class TaxonAdmin(admin.ModelAdmin[Taxon]):
    """Admin panel example for ``Taxon`` model."""

    list_display = (
        "name",
        "occurrence_count",
        "rank",
        "parent",
        "parent_names",
        "tag_list",
        "list_names",
        "created_at",
        "updated_at",
    )
    list_filter = ("lists", "rank", TaxonParentFilter)
    search_fields = ("name",)
    autocomplete_fields = (
        "parent",
        "synonym_of",
    )

    # annotate queryset with occurrence counts and allow sorting
    # https://docs.djangoproject.com/en/3.2/ref/contrib/admin/#django.contrib.admin.ModelAdmin.list_display
    # https://docs.djangoproject.com/en/3.2/ref/models/querysets/#annotate

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        return qs.annotate(occurrence_count=models.Count("occurrences")).order_by("-occurrence_count")

    @admin.display(description="Tags")
    def tag_list(self, obj) -> str:
        return ", ".join([tag.name for tag in obj.tags.all()])

    def occurrence_count(self, obj) -> int:
        return obj.occurrence_count

    # Action to update species parents
    @admin.action(description="Update species parents")
    def update_species_parents(self, request: HttpRequest, queryset: QuerySet[Taxon]) -> None:
        for taxon in queryset:
            taxon.update_parents()
        self.message_user(request, f"Updated {queryset.count()} taxa.")

    @admin.action(description="Update cached display names")
    def update_display_names(self, request: HttpRequest, queryset: QuerySet[Taxon]) -> None:
        Taxon.objects.update_display_names(queryset)

        self.message_user(request, f"Updated {queryset.count()} taxa.")

    @admin.display(
        description="Parents",
        ordering="parents",
    )
    def parent_names(self, obj) -> str:
        if obj.parents_json:
            return ", ".join([str(taxon.name) for taxon in obj.parents_json])
        else:
            return ""

    actions = [update_species_parents, update_display_names]


@admin.register(TaxaList)
class TaxaListAdmin(admin.ModelAdmin[TaxaList]):
    """Admin panel example for ``TaxaList`` model."""

    list_display = ("name", "taxa_count", "created_at", "updated_at")

    def taxa_count(self, obj) -> int:
        return obj.taxa.count()

    autocomplete_fields = (
        "taxa",
        "projects",
    )

    list_filter = ("projects",)


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin[Device]):
    """Admin panel example for ``Device`` model."""


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin[Site]):
    """Admin panel example for ``Site`` model."""


@admin.register(S3StorageSource)
class S3StorageSourceAdmin(admin.ModelAdmin[S3StorageSource]):
    """Admin panel example for ``S3StorageSource`` model."""

    list_display = (
        "name",
        "uri",
        "size",
        "total_files",
        "is_private",
        "last_checked",
        "project",
        "updated_at",
    )

    def size(self, obj) -> str:
        return filesizeformat(obj.total_size)

    @admin.display(description="S3 URI", ordering="bucket")
    def uri(self, obj) -> str:
        return obj.uri()

    @admin.display(boolean=True)
    def is_private(self, obj) -> bool:
        """
        If a public base URL is set, the source is considered public.
        """
        return not bool(obj.public_base_url)

    @admin.action()
    def calculate_size_async(self, request: HttpRequest, queryset: QuerySet[S3StorageSource]) -> None:
        queued_tasks = [tasks.calculate_storage_size.apply_async([source.pk]) for source in queryset]
        self.message_user(
            request,
            f"Calculating size & file counts for {len(queued_tasks)} source(s) background tasks: {queued_tasks}.",
        )

    @admin.action()
    def count_files(self, request: HttpRequest, queryset: QuerySet[S3StorageSource]) -> None:
        # measure the time elapsed for the action
        for source in queryset:
            source.count_files()
        self.message_user(request, f"File count calculated for {queryset.count()} source(s).")

    list_filter = ("project", "bucket")

    actions = [calculate_size_async, count_files]


@admin.register(SourceImageCollection)
class SourceImageCollectionAdmin(admin.ModelAdmin[SourceImageCollection]):
    """Admin panel example for ``SourceImageCollection`` model."""

    list_display = ("name", "image_count", "method", "kwargs", "created_at", "updated_at")
    list_filter = ("project",)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).annotate(image_count=models.Count("images"))

    @admin.display(
        description="Images",
        ordering="image_count",
    )
    def image_count(self, obj) -> int:
        return obj.image_count

    @admin.action()
    def populate_collection(self, request: HttpRequest, queryset: QuerySet[SourceImageCollection]) -> None:
        for collection in queryset:
            collection.populate_sample()
        self.message_user(request, f"Populated {queryset.count()} collection(s).")

    @admin.action()
    def populate_collection_async(self, request: HttpRequest, queryset: QuerySet[SourceImageCollection]) -> None:
        queued_tasks = [tasks.populate_collection.apply_async([collection.pk]) for collection in queryset]
        self.message_user(
            request,
            f"Populating {len(queued_tasks)} collection(s) background tasks: {queued_tasks}.",
        )

    @admin.action(description="Run Small Size Filter post-processing task (async)")
    def run_small_size_filter(self, request: HttpRequest, queryset: QuerySet[SourceImageCollection]) -> None:
        jobs = []
        for collection in queryset:
            job = Job.objects.create(
                name=f"Post-processing: SmallSizeFilter on Collection {collection.pk}",
                project=collection.project,
                job_type_key="post_processing",
                params={
                    "task": "small_size_filter",
                    "config": {
                        "source_image_collection_id": collection.pk,
                    },
                },
            )
            job.enqueue()
            jobs.append(job.pk)

        self.message_user(request, f"Queued Small Size Filter for {queryset.count()} collection(s). Jobs: {jobs}")

    actions = [
        populate_collection,
        populate_collection_async,
        run_small_size_filter,
    ]

    # Hide images many-to-many field from form. This would list all source images in the database.
    exclude = ("images",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "project")
    list_filter = ("project",)
    search_fields = ("name",)
