import logging

from django.db import models

from ami.base.models import BaseModel

logger = logging.getLogger(__name__)


class AlgorithmEvaluation(BaseModel):
    """
    How one algorithm scored against one occurrence set.

    Scores are stored rather than computed on demand because every view that shows them —
    the best model for a taxa list, a species' performance across algorithms — would
    otherwise recompute the same thing for every row.
    """

    algorithm = models.ForeignKey("ml.Algorithm", on_delete=models.CASCADE, related_name="evaluations")
    occurrence_set = models.ForeignKey("main.OccurrenceSet", on_delete=models.CASCADE, related_name="evaluations")
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
