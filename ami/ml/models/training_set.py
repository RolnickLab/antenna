import logging

from django.db import models

from ami.base.models import BaseModel

logger = logging.getLogger(__name__)


class TrainingSetMembership(BaseModel):
    """
    Records that an occurrence's crops went into one training run.

    An evaluation set is only honest if it holds nothing the model learned from, and a
    person verifying occurrences has no way to know which of them a past retrain already
    consumed. Writing it down at the moment the training set is built is the only reliable
    way to tell the two apart later.

    Kept as its own table rather than a flag on Occurrence: the same occurrence is used by
    every later retrain, so this is a list, not a yes or no.
    """

    project_accessor = "occurrence__project"

    occurrence = models.ForeignKey(
        "main.Occurrence",
        on_delete=models.CASCADE,
        related_name="training_uses",
    )
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.CASCADE,
        related_name="training_set_members",
        help_text="The training job that collected this occurrence.",
    )
    algorithm = models.ForeignKey(
        "ml.Algorithm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="training_occurrences",
        help_text=(
            "The algorithm version this occurrence helped produce. Filled in after training "
            "finishes, because the version does not exist while the training set is built."
        ),
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["occurrence", "job"],
                name="unique_training_use_per_occurrence_and_job",
            )
        ]
        indexes = [
            # The evaluation-set query is "occurrences never used for training", which reads
            # this column and nothing else.
            models.Index(fields=["occurrence"], name="training_use_occurrence_idx"),
        ]

    def __str__(self) -> str:
        return f"Occurrence #{self.occurrence_id} used by job #{self.job_id}"


def record_training_set(occurrence_ids: list[int], job) -> int:
    """
    Write down which occurrences a training run used.

    Ignores rows that already exist, so re-running a job does not fail and does not
    double-count.
    """
    memberships = [TrainingSetMembership(occurrence_id=pk, job=job) for pk in set(occurrence_ids)]
    if not memberships:
        return 0
    TrainingSetMembership.objects.bulk_create(memberships, batch_size=1000, ignore_conflicts=True)
    logger.info(f"Recorded {len(memberships)} occurrence(s) as used by training job #{job.pk}")
    return len(memberships)


def attach_algorithm(job, algorithm) -> int:
    """Point this job's records at the version it produced, once that version exists."""
    return TrainingSetMembership.objects.filter(job=job, algorithm__isnull=True).update(algorithm=algorithm)


def occurrence_ids_used_for_training(project=None) -> models.QuerySet:
    """Occurrences that any training run has already consumed."""
    rows = TrainingSetMembership.objects.all()
    if project:
        rows = rows.filter(occurrence__project=project)
    return rows.order_by().values_list("occurrence_id", flat=True).distinct()


def occurrences_safe_to_evaluate_on(project=None) -> models.QuerySet:
    """
    Verified occurrences no training run has used.

    This is the pool an evaluation set is drawn from. Scoring a model on data it learned
    from reports a number that means nothing.
    """
    from ami.main.models import Occurrence
    from ami.ml import training_data

    verified = training_data.verified_occurrence_ids(project) if project else None
    occurrences = Occurrence.objects.filter(determination__isnull=False)
    if project:
        occurrences = occurrences.filter(project=project, pk__in=verified)
    # Materialising the used ids follows the guidance in CLAUDE.md for anti-joins. Measured
    # locally (3,193 occurrences, 219 used): 1.3 ms against 15.3 ms for
    # `.exclude(training_uses__isnull=False)`. Not measured at production scale, where a
    # large id list may well turn the trade-off around.
    used = list(occurrence_ids_used_for_training(project))
    return occurrences.exclude(pk__in=used)
