"""The tables that record what an algorithm or a job produced, listed once.

Several queries ask "did this algorithm (or job) leave results here?": the occurrence algorithm filter,
the occurrence job filter, and the list of algorithms used in a project. Each builds its question from
``MODEL_OUTPUTS``, so a new output table is added in one place and every query learns about it. A model
with a foreign key to both ``ml.Algorithm`` and ``jobs.Job`` must be listed here or named in
``EXEMPT_MODELS`` (checked by a test). See #1462.

Models are named by app label and resolved lazily, so ``ami.main`` can use these builders without
importing ``ami.ml`` models at module level.
"""

import dataclasses
import functools
import operator
import typing

from django.apps import apps
from django.db.models import Exists, OuterRef, Q, QuerySet


@dataclasses.dataclass(frozen=True)
class ModelOutput:
    """One table of algorithm output, with the lookup path from its rows to each thing a query asks about."""

    model: str  # "app_label.ModelName"
    occurrence_path: str  # lookup from a row to its occurrence
    algorithm_field: str  # the foreign key naming the algorithm that wrote the row
    job_field: str
    # Lookup from a row to its project: the cheapest path, which is the table's own project
    # column when it has one.
    project_path: str
    # Set on a table whose rows hang off another output's rows (classifications off detections): the
    # model of that output, and the relation from its rows to this table's. The algorithm query then
    # asks both in one EXISTS. Separate EXISTS joined by OR cannot become a semi-join, and Postgres
    # then builds each one's matches for the whole table; one EXISTS keeps the per-occurrence lookup.
    # See #1462.
    folded_into: str = ""
    folded_path: str = ""

    @property
    def model_class(self):
        return apps.get_model(self.model)

    def from_job(self, job_id: int) -> Exists:
        """Whether the outer occurrence has a row here written by the job."""
        return Exists(
            self.model_class.objects.filter(**{self.occurrence_path: OuterRef("pk"), self.job_field: job_id})
        )

    def algorithms_in_project(self, project) -> QuerySet:
        """The distinct ids of the algorithms with a row here in the project (lazy; may include None)."""
        # ``order_by()`` clears the model's default ordering, which would otherwise widen the DISTINCT
        # back to one row per result.
        return (
            self.model_class.objects.filter(**{self.project_path: project})
            .order_by()
            .values_list(self.algorithm_field, flat=True)
            .distinct()
        )


MODEL_OUTPUTS: tuple[ModelOutput, ...] = (
    ModelOutput(
        model="main.Detection",
        occurrence_path="occurrence",
        algorithm_field="detection_algorithm",
        job_field="job",
        project_path="source_image__project",
    ),
    ModelOutput(
        model="main.Classification",
        occurrence_path="detection__occurrence",
        algorithm_field="algorithm",
        job_field="job",
        project_path="detection__source_image__project",
        folded_into="main.Detection",
        folded_path="classifications",
    ),
    ModelOutput(
        model="ml.AlgorithmResult",
        occurrence_path="occurrence",
        algorithm_field="algorithm",
        job_field="job",
        project_path="project",
    ),
    ModelOutput(
        model="ml.DetectionEmbedding",
        occurrence_path="detection__occurrence",
        algorithm_field="algorithm",
        job_field="job",
        project_path="project",
    ),
)

# Models with foreign keys to both ``ml.Algorithm`` and ``jobs.Job`` that are not output tables, each
# with the reason it is left out.
EXEMPT_MODELS: dict[str, str] = {}


def occurrences_from_algorithms(algorithm_ids) -> Q:
    """Matches occurrences with a result from any of the algorithms, in any output table."""
    conditions = {
        output.model: Q(**{f"{output.algorithm_field}__in": algorithm_ids})
        for output in MODEL_OUTPUTS
        if not output.folded_into
    }
    for output in MODEL_OUTPUTS:
        if output.folded_into:
            conditions[output.folded_into] |= Q(
                **{f"{output.folded_path}__{output.algorithm_field}__in": algorithm_ids}
            )
    return _any_of(
        Exists(
            output.model_class.objects.filter(**{output.occurrence_path: OuterRef("pk")}).filter(
                conditions[output.model]
            )
        )
        for output in MODEL_OUTPUTS
        if not output.folded_into
    )


def occurrences_from_job(job_id: int) -> Q:
    """Matches occurrences with a result written by the job, in any output table."""
    return _any_of(output.from_job(job_id) for output in MODEL_OUTPUTS)


def algorithm_ids_in_project(project) -> list[int]:
    """The ids of the algorithms with a result in the project, in any output table.

    Runs one query per table immediately; each list holds one id per algorithm, and the merged result
    is sorted so the SQL built from it, and therefore cachalot's cache key, is stable.
    """
    ids: set[int | None] = set()
    for output in MODEL_OUTPUTS:
        ids.update(output.algorithms_in_project(project))
    ids.discard(None)  # detections without a detection_algorithm
    return sorted(typing.cast(set[int], ids))


def _any_of(conditions: typing.Iterable[Exists]) -> Q:
    return functools.reduce(operator.or_, conditions)
