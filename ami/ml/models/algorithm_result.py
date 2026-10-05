import collections
import logging
import typing

from django.apps import apps
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from ami.base.models import BaseModel, BaseQuerySet
from ami.ml.results.schemas import validate_result_data

if typing.TYPE_CHECKING:
    from ami.main.models import Occurrence

logger = logging.getLogger(__name__)


class AlgorithmResultQuerySet(BaseQuerySet):
    def current(self):
        return self.filter(is_current=True)

    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        for obj in objs:
            obj.data = validate_result_data(obj.kind, obj.data)
        return super().bulk_create(objs, *args, **kwargs)

    def bulk_update(self, objs, fields, *args, **kwargs):
        objs = list(objs)
        if "data" in fields:
            for obj in objs:
                obj.data = validate_result_data(obj.kind, obj.data)
        return super().bulk_update(objs, fields, *args, **kwargs)

    def record(self, **fields) -> "AlgorithmResult":
        """Insert one result as the current one for its occurrence, algorithm and kind."""
        results = self.record_many([self.model(**fields)])
        if not results:
            raise ValueError("The occurrence has no project.")
        return results[0]

    def record_many(self, results: typing.Iterable["AlgorithmResult"]) -> list["AlgorithmResult"]:
        """Insert results as current, keeping each occurrence's earlier result of the same algorithm and kind.

        Rows are only inserted, never rewritten, apart from clearing ``is_current`` on the result
        each new one replaces. A result whose occurrence has no project is skipped with a warning
        rather than failing a run that has already changed data. The returned list holds the
        results that were written, in order.
        """
        results = list(results)
        if not results:
            return []
        kept: list[AlgorithmResult] = []
        groups: dict[tuple[int, str], set[int]] = collections.defaultdict(set)
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
            key = (result.algorithm_id, result.kind)
            if result.occurrence_id in groups[key]:
                raise ValueError(
                    f"Two {result.kind} results for Occurrence #{result.occurrence_id} "
                    "from one algorithm in one write."
                )
            groups[key].add(result.occurrence_id)
            result.is_current = True
            kept.append(result)
        if not kept:
            return []
        with transaction.atomic():
            # Lock the occurrences in a stable order, so two runs writing results for the same
            # occurrence wait for each other instead of both inserting a current row.
            list(
                apps.get_model("main", "Occurrence")
                .objects.select_for_update()
                .filter(pk__in={result.occurrence_id for result in kept})
                .order_by("pk")
                .values_list("pk", flat=True)
            )
            for (algorithm_id, kind), occurrence_ids in groups.items():
                self.filter(
                    occurrence_id__in=occurrence_ids, algorithm_id=algorithm_id, kind=kind, is_current=True
                ).update(is_current=False)
            return self.bulk_create(kept)

    def move_to_occurrence(self, kept: "Occurrence", absorbed_ids: typing.Iterable[int]) -> int:
        """Move the results of occurrences merged into ``kept``, so their history follows the merge.

        Each algorithm and kind keeps one current result on ``kept``: its own if it has one,
        otherwise the latest moved one. The other moved results stay as history. Returns the
        number of results moved.
        """
        absorbed_ids = set(absorbed_ids) - {kept.pk}
        if not absorbed_ids:
            return 0
        with transaction.atomic():
            current_keys = set(self.filter(occurrence=kept, is_current=True).values_list("algorithm_id", "kind"))
            demote: list[int] = []
            for pk, algorithm_id, kind in (
                self.filter(occurrence_id__in=absorbed_ids, is_current=True)
                .order_by("-timestamp", "-pk")
                .values_list("pk", "algorithm_id", "kind")
            ):
                if (algorithm_id, kind) in current_keys:
                    demote.append(pk)
                else:
                    current_keys.add((algorithm_id, kind))
            if demote:
                self.filter(pk__in=demote).update(is_current=False)
            return self.filter(occurrence_id__in=absorbed_ids).update(occurrence=kept)


@typing.final
class AlgorithmResult(BaseModel):
    """What a post-processing run decided about one occurrence: a record of the run, never an input to it.

    The determination never reads this table. A run that changes an occurrence's taxon does so
    through the ``Classification`` rows it creates, and those rows point back here through
    ``Classification.algorithm_result`` so the history can show a run with what it changed.
    ``data`` holds the run's own figures, validated against the model for ``kind``
    (ami/ml/results/schemas.py), and ``value`` repeats the one figure lists filter and sort on. The
    ``extra`` object inside ``data`` is stored, shown and exported only; nothing reads it for
    logic, and a value a feature needs becomes a typed field. A new result for the same
    occurrence, algorithm and kind becomes the current one and the earlier ones stay as
    history. Write through ``AlgorithmResult.objects.record`` or ``record_many``. Tracking and
    rank roll-ups are the next kinds expected. See #1431.
    """

    class Kind(models.TextChoices):
        CLASS_MASKING = "class_masking"
        SIZE_FILTER = "size_filter"

    # Copied from the occurrence when the result is written, so per-project
    # queries and permission checks need no join.
    project = models.ForeignKey("main.Project", on_delete=models.CASCADE, related_name="algorithm_results")
    # Indexed together with the timestamp, below.
    occurrence = models.ForeignKey(
        "main.Occurrence", on_delete=models.CASCADE, related_name="algorithm_results", db_index=False
    )
    algorithm = models.ForeignKey("ml.Algorithm", on_delete=models.CASCADE, related_name="algorithm_results")
    # The run that wrote the result. Deleting the job keeps the result, with no run to link to.
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="algorithm_results"
    )
    # No ``choices``: the registry of data models in ami/ml/results/schemas.py is the list of kinds,
    # and every write path rejects a kind without one, so a new kind needs no migration.
    kind = models.CharField(max_length=32)
    # The kind's headline figure, for filtering and sorting: the share of probability outside
    # the list for class masking, the relative size for the size filter.
    value = models.FloatField(null=True, blank=True)
    data = models.JSONField(default=dict, blank=True)
    is_current = models.BooleanField(default=True)
    timestamp = models.DateTimeField(default=timezone.now)

    objects = AlgorithmResultQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["occurrence", "algorithm", "kind"],
                condition=Q(is_current=True),
                name="algorithm_result_current_occurrence",
            ),
        ]
        indexes = [
            models.Index(fields=["occurrence", "-timestamp"], name="algorithm_result_occ_time"),
            models.Index(
                fields=["project", "kind", "value"],
                condition=Q(is_current=True, value__isnull=False),
                name="algorithm_result_current_value",
            ),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} {self.kind} for Occurrence #{self.occurrence_id} from Algorithm #{self.algorithm_id}"

    def save(self, *args, **kwargs):
        self.data = validate_result_data(self.kind, self.data)
        if self.project_id is None:
            self.project_id = self.occurrence.project_id
        if self.project_id is None:
            raise ValueError("The occurrence has no project.")
        super().save(*args, **kwargs)
