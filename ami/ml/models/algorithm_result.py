import logging
import typing

from django.db import models
from django.db.models import Q
from django.utils import timezone

from ami.base.models import BaseModel, BaseQuerySet
from ami.ml.results.schemas import result_value, validate_result_data

if typing.TYPE_CHECKING:
    from ami.main.models import Occurrence

logger = logging.getLogger(__name__)


class AlgorithmResultQuerySet(BaseQuerySet):
    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        for obj in objs:
            obj.fill_from_data()
        return super().bulk_create(objs, *args, **kwargs)

    def bulk_update(self, objs, fields, *args, **kwargs):
        objs = list(objs)
        if "data" in fields:
            for obj in objs:
                obj.fill_from_data()
            fields = [*fields, "value"] if "value" not in fields else fields
        return super().bulk_update(objs, fields, *args, **kwargs)

    def record(self, **fields) -> "AlgorithmResult":
        """Insert one result."""
        results = self.record_many([self.model(**fields)])
        if not results:
            raise ValueError("The occurrence has no project.")
        return results[0]

    def record_many(self, results: typing.Iterable["AlgorithmResult"]) -> list["AlgorithmResult"]:
        """Insert results, each with its project copied from its occurrence.

        Results are only ever added: a later run's result sits beside the earlier ones. A result
        whose occurrence has no project is skipped with a warning rather than failing a run that
        has already changed data. The returned list holds the results that were written, in order.
        """
        kept: list[AlgorithmResult] = []
        for result in results:
            if result.project_id is None:
                result.project_id = result.occurrence.project_id
            if result.project_id is None:
                # Occurrences without a project are a data problem tracked on #1188; skipping keeps the run going.
                logger.warning(
                    f"Not recording the {result.kind} result for Occurrence #{result.occurrence_id}: "
                    "it has no project."
                )
                continue
            kept.append(result)
        return self.bulk_create(kept) if kept else []

    def move_to_occurrence(self, kept: "Occurrence", absorbed_ids: typing.Iterable[int]) -> int:
        """Move the results of occurrences merged into ``kept``, so their history follows the merge.

        Call it before deleting the absorbed occurrences, whose results would otherwise be deleted
        with them. Occurrences of another project are refused, so a result never ends up filed under
        a project other than its occurrence's. Returns the number of results moved.
        """
        absorbed_ids = set(absorbed_ids) - {kept.pk}
        if not absorbed_ids:
            return 0
        occurrences = self.model._meta.get_field("occurrence").related_model.objects
        if occurrences.filter(pk__in=absorbed_ids).exclude(project_id=kept.project_id).exists():
            raise ValueError(f"Cannot move results into Occurrence #{kept.pk} from occurrences of another project.")
        return self.filter(occurrence_id__in=absorbed_ids).update(occurrence=kept)


@typing.final
class AlgorithmResult(BaseModel):
    """What a post-processing run decided about one occurrence, with the figures only that run knew.

    The determination never reads this table. A run that changes an occurrence's taxon does so
    through the ``Classification`` rows it creates, and those rows point back here through
    ``Classification.algorithm_result`` so the history can show a run with what it changed.
    ``data`` holds the run's own figures, validated against the model for ``kind``
    (ami/ml/results/schemas.py), and ``value`` repeats the one figure lists filter and sort on. The
    ``extra`` object inside ``data`` is stored, shown and exported only; nothing reads it for
    logic, and a value a feature needs becomes a typed field. Every run adds its own result,
    so running a method twice leaves two results on the occurrence, one per job. Write through
    ``AlgorithmResult.objects.record`` or ``record_many``. Rank roll-ups are the next kind
    expected. See #1431.
    """

    # Copied from the occurrence when the result is written, so per-project
    # queries and permission checks need no join.
    project = models.ForeignKey("main.Project", on_delete=models.CASCADE, related_name="algorithm_results")
    # Indexed together with the timestamp, below.
    occurrence = models.ForeignKey(
        "main.Occurrence", on_delete=models.CASCADE, related_name="algorithm_results", db_index=False
    )
    algorithm = models.ForeignKey("ml.Algorithm", on_delete=models.CASCADE, related_name="algorithm_results")
    # The run that wrote the result. Deleting the job keeps the result, with no run to link to.
    # Indexed together with the occurrence, below.
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="algorithm_results", db_index=False
    )
    # No ``choices``: the registry of data models in ami/ml/results/schemas.py is the list of kinds,
    # and every write path rejects a kind without one, so a new kind needs no migration.
    kind = models.CharField(max_length=32)
    # The kind's headline figure, for filtering and sorting, copied from the data field its model
    # names in ``value_field`` on every write.
    value = models.FloatField(null=True, blank=True)
    data = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    objects = AlgorithmResultQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=["occurrence", "-timestamp"], name="algorithm_result_occ_time"),
            models.Index(
                fields=["project", "kind", "value"],
                condition=Q(value__isnull=False),
                name="algorithm_result_value",
            ),
            # Leads with the job, for the ?job= occurrence filter and for deleting a job.
            models.Index(fields=["job", "occurrence"], name="algorithm_result_job_occ"),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} {self.kind} for Occurrence #{self.occurrence_id} from Algorithm #{self.algorithm_id}"

    def fill_from_data(self) -> None:
        """Validate ``data`` against the kind's model and set ``value`` to the figure the kind names."""
        self.data = validate_result_data(self.kind, self.data)
        self.value = result_value(self.kind, self.data)

    def save(self, *args, **kwargs):
        self.fill_from_data()
        if self.project_id is None:
            self.project_id = self.occurrence.project_id
        if self.project_id is None:
            raise ValueError("The occurrence has no project.")
        super().save(*args, **kwargs)
