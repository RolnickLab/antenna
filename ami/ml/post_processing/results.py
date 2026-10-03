"""One algorithm result per occurrence a post-processing run touches, written inside each batch.

A run that re-scores or flags detections changes classifications and determinations in batches,
each in its own transaction. ``BatchResults`` writes the result rows in those same transactions,
so a batch either lands with its results or not at all. Every occurrence the run touches gets
exactly one current result: it is created by the first batch that touches the occurrence, before
the classifications that batch inserts so they can point at it, and later batches extend it with
the detections they changed and the determination after their saves.
"""

from __future__ import annotations

import collections
import datetime
import typing

from ami.main.models import AlgorithmResult, Classification, Occurrence

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job
    from ami.ml.models import Algorithm


class BatchResults:
    def __init__(
        self,
        *,
        kind: str,
        algorithm: Algorithm,
        job: Job | None,
        data: dict,
        timestamp: datetime.datetime | None = None,
    ):
        """``data`` holds the fields every result of the run shares, such as the settings it ran with."""
        self.kind = kind
        self.algorithm = algorithm
        self.job = job
        self.data = data
        self.timestamp = timestamp
        self.results: dict[int, AlgorithmResult] = {}
        # Occurrences with no project, directly or through their station; tried once, then left alone.
        self.skipped: set[int] = set()
        self.changed_detections: dict[int, set[int]] = collections.defaultdict(set)

    def note(self, occurrence: Occurrence, detection_id: int) -> None:
        """Record that the run changed one of the occurrence's detections, ahead of the batch write."""
        self.changed_detections[occurrence.pk].add(detection_id)

    def start_batch(self, occurrences: typing.Iterable[Occurrence], classifications: typing.Iterable[Classification]):
        """Create the results for occurrences the run has not seen and point the batch's new classifications at theirs.

        Call inside the batch transaction, before the classifications are inserted and before the
        occurrences are saved, so a result's ``taxon_before_id`` is the determination the run found.
        """
        new = [o for o in occurrences if o.pk not in self.results and o.pk not in self.skipped]
        written = AlgorithmResult.objects.record_many(
            AlgorithmResult(
                occurrence=occurrence,
                algorithm=self.algorithm,
                job=self.job,
                kind=self.kind,
                data={
                    **self.data,
                    "detection_ids": [],
                    "taxon_before_id": occurrence.determination_id,
                    "taxon_after_id": None,
                },
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
        """Record each occurrence's determination after the batch's saves and the detections changed so far."""
        touched = []
        for occurrence in occurrences:
            result = self.results.get(occurrence.pk)
            if result is None:
                continue
            changed = self.changed_detections.pop(occurrence.pk, set())
            result.data["detection_ids"] = sorted(set(result.data["detection_ids"]) | changed)
            result.data["taxon_after_id"] = occurrence.determination_id
            touched.append(result)
        if touched:
            AlgorithmResult.objects.bulk_update(touched, ["data"])
