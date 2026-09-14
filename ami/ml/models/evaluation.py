import logging

from django.db import models

from ami.base.models import BaseModel, BaseQuerySet

logger = logging.getLogger(__name__)


class OccurrenceSetQuerySet(BaseQuerySet):
    def for_project(self, project) -> models.QuerySet:
        """Sets this project can use: its own, plus any that belong to no project."""
        return self.filter(models.Q(projects=project) | models.Q(projects__isnull=True)).distinct()


class OccurrenceSet(BaseModel):
    """
    A fixed list of occurrences to score models against.

    Two models can only be compared if they were scored on the same occurrences, so the
    membership is stored rather than re-sampled. A set with no projects is global, which is
    how one set compares models across the platform; that follows how TaxaList already
    treats a list with no project.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    occurrences = models.ManyToManyField("main.Occurrence", related_name="evaluation_sets", blank=True)
    projects = models.ManyToManyField(
        "main.Project",
        related_name="occurrence_sets",
        blank=True,
        help_text="Projects this set belongs to. A set with none is available everywhere.",
    )

    objects = OccurrenceSetQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.occurrences.count()} occurrences)"

    @property
    def is_global(self) -> bool:
        return not self.projects.exists()


class AlgorithmEvaluation(BaseModel):
    """
    How one algorithm scored against one occurrence set.

    Scores are stored rather than computed on demand because every view that shows them —
    the best model for a taxa list, a species' performance across algorithms — would
    otherwise recompute the same thing for every row.
    """

    algorithm = models.ForeignKey("ml.Algorithm", on_delete=models.CASCADE, related_name="evaluations")
    occurrence_set = models.ForeignKey(OccurrenceSet, on_delete=models.CASCADE, related_name="evaluations")
    job = models.ForeignKey("jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="evaluations")

    micro_accuracy = models.FloatField(null=True, help_text="Share of occurrences the algorithm named correctly.")
    macro_accuracy = models.FloatField(
        null=True,
        help_text=(
            "Mean of the per-species accuracies. Trap data is long-tailed, so this says "
            "far more than the plain share about whether rare species are handled."
        ),
    )
    occurrences_scored = models.PositiveIntegerField(default=0)
    occurrences_skipped = models.PositiveIntegerField(
        default=0,
        help_text=(
            "In the set but not scored, because the species is outside what this algorithm "
            "can predict. Scoring those would punish it for a question it was never asked."
        ),
    )
    species_scored = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["algorithm", "occurrence_set"],
                name="unique_evaluation_per_algorithm_and_set",
            )
        ]

    def __str__(self) -> str:
        return f"{self.algorithm} on {self.occurrence_set}: {self.micro_accuracy}"


class TaxonEvaluation(BaseModel):
    """
    How one algorithm did on one species, within one evaluation.

    The per-species breakdown the taxon page shows. Kept as rows rather than a blob so it
    can be queried the other way round: every algorithm's score for a given species.
    """

    evaluation = models.ForeignKey(AlgorithmEvaluation, on_delete=models.CASCADE, related_name="taxa")
    taxon = models.ForeignKey("main.Taxon", on_delete=models.CASCADE, related_name="evaluations")

    accuracy = models.FloatField(help_text="Share of this species' occurrences the algorithm named correctly.")
    occurrences_scored = models.PositiveIntegerField(default=0)
    correct = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-occurrences_scored", "taxon__name"]
        constraints = [models.UniqueConstraint(fields=["evaluation", "taxon"], name="unique_taxon_per_evaluation")]

    def __str__(self) -> str:
        return f"{self.taxon}: {self.accuracy}"
