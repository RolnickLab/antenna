from typing import Any

from django.contrib import admin
from django.db import models
from django.db.models.query import QuerySet
from django.http.request import HttpRequest
from django.template.defaultfilters import filesizeformat
from django.utils.formats import number_format

import ami.utils
from ami import tasks

from .models import (
    BlogPost,
    Deployment,
    Device,
    Event,
    Occurrence,
    Project,
    S3StorageSource,
    Site,
    SourceImage,
    TaxaList,
    Taxon,
)


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin[BlogPost]):
    """Admin panel example for ``BlogPost`` model."""


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin[Project]):
    """Admin panel example for ``Project`` model."""


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

    actions = [sync_captures]

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
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        qs = super().get_queryset(request)
        from django.db.models import ExpressionWrapper, F
        from django.db.models.fields import DurationField

        return qs.select_related("deployment", "project").annotate(
            captures_count=models.Count("captures"),
            time_duration=ExpressionWrapper(F("end") - F("start"), output_field=DurationField()),
        )

    @admin.display(
        description="Duration",
        ordering="time_duration",
    )
    def duration_display(self, obj) -> str:
        return ami.utils.dates.format_timedelta(obj.time_duration)

    # Save all events in queryset
    @admin.action(description="Re-save events to update cached values")
    def save_events(self, request: HttpRequest, queryset: QuerySet[Event]) -> None:
        for event in queryset:
            event.save()
        self.message_user(request, f"Updated {queryset.count()} events.")

    list_filter = ("deployment", "project", "start")
    actions = [save_events]


@admin.register(SourceImage)
class SourceImageAdmin(admin.ModelAdmin[SourceImage]):
    """Admin panel example for ``SourceImage`` model."""

    list_display = (
        "path",
        "timestamp",
        "event",
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
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).select_related("event", "deployment", "deployment__data_source")


@admin.register(Occurrence)
class OccurrenceAdmin(admin.ModelAdmin[Occurrence]):
    """Admin panel example for ``Occurrence`` model."""

    list_display = ("id", "determination", "project", "deployment", "event")

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        qs = super().get_queryset(request)
        return qs.select_related("determination", "project", "deployment", "event")


class TaxonParentFilter(admin.SimpleListFilter):
    """
    Return all taxa that are not species.
    """

    title = "Taxon parent"
    parameter_name = "parent"

    def lookups(self, request, model_admin):
        # return Taxon.objects.exclude(rank="SPECIES").values_list("id", "name")
        choices = [(taxon.id, str(taxon)) for taxon in Taxon.objects.exclude(rank="SPECIES")]
        return choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(parent__id=self.value())
        return queryset


@admin.register(Taxon)
class TaxonAdmin(admin.ModelAdmin[Taxon]):
    """Admin panel example for ``Taxon`` model."""

    list_display = ("name", "occurrence_count", "rank", "parent", "list_names")
    list_filter = ("rank", TaxonParentFilter)
    search_fields = ("name",)

    # annotate queryset with occurrence counts and allow sorting
    # https://docs.djangoproject.com/en/3.2/ref/contrib/admin/#django.contrib.admin.ModelAdmin.list_display
    # https://docs.djangoproject.com/en/3.2/ref/models/querysets/#annotate

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        return qs.annotate(occurrence_count=models.Count("occurrences")).order_by("-occurrence_count")

    @admin.display(
        description="Occurrences",
        ordering="occurrence_count",
    )
    def occurrence_count(self, obj) -> int:
        return obj.occurrence_count


@admin.register(TaxaList)
class TaxaListAdmin(admin.ModelAdmin[TaxaList]):
    """Admin panel example for ``TaxaList`` model."""

    list_display = ("name", "taxa_count", "created_at", "updated_at")

    def taxa_count(self, obj) -> int:
        return obj.taxa.count()


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin[Device]):
    """Admin panel example for ``Device`` model."""


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin[Site]):
    """Admin panel example for ``Site`` model."""


@admin.register(S3StorageSource)
class S3StorageSourceAdmin(admin.ModelAdmin[S3StorageSource]):
    """Admin panel example for ``S3StorageSource`` model."""

    list_display = ("name", "bucket", "prefix", "size", "total_files", "last_checked")

    def size(self, obj) -> str:
        return filesizeformat(obj.total_size)

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

    actions = [calculate_size_async, count_files]
