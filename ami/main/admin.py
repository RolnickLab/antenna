from typing import Any

from django.contrib import admin
from django.db.models import Count
from django.db.models.query import QuerySet
from django.http.request import HttpRequest

from .models import BlogPost, Deployment, Device, Occurrence, Project, Site, SourceImage, TaxaList, Taxon


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin[BlogPost]):
    """Admin panel example for ``BlogPost`` model."""


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin[Project]):
    """Admin panel example for ``Project`` model."""


@admin.register(Deployment)
class DeploymentAdmin(admin.ModelAdmin[Deployment]):
    """Admin panel example for ``Deployment`` model."""


@admin.register(SourceImage)
class SourceImageAdmin(admin.ModelAdmin[SourceImage]):
    """Admin panel example for ``SourceImage`` model."""


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

        return qs.annotate(occurrence_count=Count("occurrences")).order_by("-occurrence_count")

    @admin.display(
        description="Occurrences",
        ordering="occurrence_count",
    )
    def occurrence_count(self, obj) -> int:
        return obj.occurrence_count


@admin.register(TaxaList)
class TaxaListAdmin(admin.ModelAdmin[TaxaList]):
    """Admin panel example for ``TaxaList`` model."""

    def taxa_count(self, obj) -> int:
        return obj.taxa.count()

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
    )

    list_filter = (
        "deployment",
        "timestamp",
    )


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin[Device]):
    """Admin panel example for ``Device`` model."""


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin[Site]):
    """Admin panel example for ``Site`` model."""
