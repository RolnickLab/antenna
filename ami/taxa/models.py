import datetime
import functools
import logging
import typing as t

from django.db import models, transaction
from django.utils import timezone

from ami.base.models import BaseModel, update_calculated_fields_in_bulk
from ami.main.models import Classification, Detection, Occurrence, Project, Taxon

logger = logging.getLogger(__name__)

# Create your models here.


@t.final
class TaxonObserved(BaseModel):
    """
    A record of a taxon that was detected or identified in a Project.

    Should be fast to retrieve and cache any counts or other aggregate values.
    """

    taxon = models.ForeignKey(Taxon, on_delete=models.CASCADE, related_name="observations")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="taxa_observed")
    occurrences = models.ManyToManyField(Occurrence, related_name="taxa_observed")
    detections = models.ManyToManyField(Detection, related_name="taxa_observed")

    # Pre-calculated fields
    detections_count = models.IntegerField(default=0)
    occurrences_count = models.IntegerField(default=0)
    best_determination_score = models.FloatField(null=True, blank=True)
    best_detection = models.ForeignKey(Detection, on_delete=models.SET_NULL, null=True, blank=True)
    last_detected = models.DateTimeField(null=True, blank=True)
    calculated_fields_updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-last_detected"]
        verbose_name_plural = "Taxa Observed"

    def __str__(self) -> str:
        return f"{self.taxon} in {self.project}"

    def get_detections_count(self) -> int:
        return Detection.objects.filter(
            occurrence__determination=self.taxon,
            occurrence__project=self.project,
        ).count()

    def get_occurrences_count(self) -> int:
        return Occurrence.objects.filter(
            determination=self.taxon,
            project=self.project,
        ).count()

    def get_best_detection(self) -> Detection | None:
        return (
            Detection.objects.filter(occurrence__determination=self.taxon, occurrence__project=self.project)
            .order_by("-classifications__score")
            .first()
        )

    def get_best_determination_score(self) -> float | None:
        return (
            Classification.objects.filter(
                detection__occurrence__determination=self.taxon, detection__occurrence__project=self.project
            )
            .order_by("-score")
            .values_list("score", flat=True)
            .first()
        )

    def get_last_detected(self) -> datetime.datetime | None:
        return (
            Detection.objects.filter(occurrence__determination=self.taxon, occurrence__project=self.project)
            .order_by("-timestamp")
            .values_list("timestamp", flat=True)
            .first()
        )

    def update_calculated_fields(self, save=True, updated_timestamp: datetime.datetime | None = None):
        """
        Update the counts and timestamps of detections, identifications, and occurrences.
        """
        self.detections_count = self.get_detections_count()
        self.occurrences_count = self.get_detections_count()
        self.best_detection = self.get_best_detection()
        self.best_determination_score = self.get_best_determination_score()
        self.last_detected = self.get_last_detected()
        self.calculated_fields_updated_at = updated_timestamp or timezone.now()

        if save:
            self.save(update_calculated_fields=False)

    def save(self, update_calculated_fields=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.pk and update_calculated_fields:
            self.update_calculated_fields(save=True)


update_calculated_fields_for_taxa_observed = functools.partial(
    update_calculated_fields_in_bulk,
    Model=TaxonObserved,
    fields=[
        "detections_count",
        "occurrences_count",
        "best_detection",
        "best_determination_score",
        "last_detected",
        "calculated_fields_updated_at",
    ],
)


def create_taxon_observed_for_project(taxon: Taxon, project: Project) -> tuple[TaxonObserved, bool]:
    """
    Create a TaxonObserved record for a Taxon in a Project.

    This is used to cache aggregate values for a taxon in a project.
    """
    taxon_observed, created = TaxonObserved.objects.get_or_create(taxon=taxon, project=project)
    return taxon_observed, created


def update_taxa_observed_for_project(project: Project) -> list[TaxonObserved]:
    """
    Find all taxa observed in a project and create TaxonObserved records for them.

    Create new records in bulk and remove records for taxa no longer in the project.
    Does not update existing records.
    """
    # Get all existing TaxonObserved records for the project
    existing_observed = set(TaxonObserved.objects.filter(project=project).values_list("taxon_id", flat=True))

    # Find taxa that have occurrences in the project but don't have a TaxonObserved record
    taxa_to_create = Taxon.objects.filter(occurrences__project=project).exclude(id__in=existing_observed).distinct()

    # @TODO create & update parent taxa counts (Genus, Family, etc. records)

    # Prepare TaxonObserved objects for bulk creation
    to_create = [
        TaxonObserved(
            taxon_id=taxon.id,
            project=project,
        )
        for taxon in taxa_to_create
    ]

    # Find taxa that no longer have occurrences in the project
    taxa_still_in_project = Taxon.objects.filter(occurrences__project=project).values("id")
    to_delete_ids = (
        TaxonObserved.objects.filter(project=project)
        .exclude(taxon_id__in=taxa_still_in_project)
        .values_list("id", flat=True)
    )

    # Use a transaction to ensure atomicity
    with transaction.atomic():
        # Bulk create new records
        created = TaxonObserved.objects.bulk_create(to_create)

        # Delete records for taxa no longer in the project
        # TaxonObserved.objects.filter(id__in=to_delete_ids).delete()
        deleted_count, _ = TaxonObserved.objects.filter(id__in=to_delete_ids).delete()

    updated_count = update_calculated_fields_for_taxa_observed(
        qs=TaxonObserved.objects.filter(project=project),  # type: ignore
    )

    logger.info(f"Created {len(created)} TaxonObserved records for {project}")
    logger.info(f"Deleted {deleted_count} TaxonObserved records for {project}")
    logger.info(f"Updated {updated_count} TaxonObserved records for {project}")

    return created
