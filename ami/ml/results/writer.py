"""One algorithm result per occurrence a post-processing run touches, written inside each batch.

A run that re-scores or flags detections changes classifications and determinations in batches,
each in its own transaction. ``AlgorithmResultWriter`` writes the result rows in those same transactions,
so a batch either lands with its results or not at all. Every occurrence the run touches gets
exactly one current result: it is created by the first batch that touches the occurrence, before
the classifications that batch inserts so they can point at it, and later batches update it with
the figures of the detection that represents the occurrence and the determination after their
saves.
"""

from __future__ import annotations

import datetime
import typing

from ami.ml.models import AlgorithmResult

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job
    from ami.main.models import Classification, Occurrence
    from ami.ml.models import Algorithm


class AlgorithmResultWriter:
    def __init__(
        self,
        *,
        kind: str,
        algorithm: Algorithm,
        job: Job | None,
        value_field: str,
        timestamp: datetime.datetime | None = None,
    ):
        """``value_field`` names the figure in the result's data that is also stored in ``value``."""
        self.kind = kind
        self.algorithm = algorithm
        self.job = job
        self.value_field = value_field
        self.timestamp = timestamp
        self.results: dict[int, AlgorithmResult] = {}
        # Occurrences with no project; tried once, then left alone.
        self.skipped: set[int] = set()
        # Per occurrence, the figures of the detection that represents it so far, with their rank.
        self.figures: dict[int, tuple[float, dict]] = {}

    def note(self, occurrence: Occurrence, figures: dict, rank: float) -> None:
        """Offer one changed detection's figures for the occurrence; the highest ``rank`` wins the result."""
        current = self.figures.get(occurrence.pk)
        if current is None or rank > current[0]:
            self.figures[occurrence.pk] = (rank, figures)

    def start_batch(self, occurrences: typing.Iterable[Occurrence], classifications: typing.Iterable[Classification]):
        """Create the results for occurrences the run has not seen and point the batch's new classifications at theirs.

        Call inside the batch transaction, before the classifications are inserted and before the
        occurrences are saved, so a result's ``determination_before_id`` is what the run found.
        """
        new = [o for o in occurrences if o.pk not in self.results and o.pk not in self.skipped]
        written = AlgorithmResult.objects.record_many(
            AlgorithmResult(
                occurrence=occurrence,
                algorithm=self.algorithm,
                job=self.job,
                kind=self.kind,
                value=self.figures[occurrence.pk][1][self.value_field],
                data={**self.figures[occurrence.pk][1], "determination_before_id": occurrence.determination_id},
                **({"timestamp": self.timestamp} if self.timestamp else {}),
            )
            for occurrence in new
        )
        for result in written:
            self.results[result.occurrence_id] = result
        self.skipped.update(o.pk for o in new if o.pk not in self.results)
        for classification in classifications:
            classification.algorithm_result = self.results.get(classification.detection.occurrence_id)

    def finish_batch(self, occurrences: typing.Iterable[Occurrence]) -> None:
        """Record each occurrence's determination after the batch's saves and its best figures so far."""
        touched = []
        for occurrence in occurrences:
            result = self.results.get(occurrence.pk)
            if result is None:
                continue
            figures = self.figures[occurrence.pk][1]
            result.data = {**result.data, **figures, "determination_after_id": occurrence.determination_id}
            result.value = figures[self.value_field]
            touched.append(result)
        if touched:
            AlgorithmResult.objects.bulk_update(touched, ["data", "value"])
