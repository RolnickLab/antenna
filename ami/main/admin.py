from django.contrib import admin

from .models import BlogPost, Deployment, Project, SourceImage, TaxaList, Taxon


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

    list_display = ("name", "rank", "parent", "ordering", "list_names")
    list_filter = ("rank", TaxonParentFilter)
    search_fields = ("name",)


@admin.register(TaxaList)
class TaxaListAdmin(admin.ModelAdmin[TaxaList]):
    """Admin panel example for ``TaxaList`` model."""

    list_display = ("name", "taxa_count", "created_at", "updated_at")

    def taxa_count(self, obj) -> int:
        return obj.taxa.count()
