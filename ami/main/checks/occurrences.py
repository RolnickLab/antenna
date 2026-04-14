"""Integrity checks for Occurrence records."""

import dataclasses
import logging

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class IntegrityCheckResult:
    checked: int = 0
    fixed: int = 0
    unfixable: int = 0


def get_occurrences_missing_determination(
    project_id: int | None = None,
    job_id: int | None = None,
):
    """Return occurrences that have classifications but no determination set.

    Occurrences without any classifications are excluded because they
    legitimately have no determination yet.
    """
    from ami.main.models import Occurrence

    qs = Occurrence.objects.filter(
        determination__isnull=True,
        detections__classifications__isnull=False,
    ).distinct()

    if project_id is not None:
        qs = qs.filter(project_id=project_id)

    if job_id is not None:
        from ami.jobs.models import Job

        job = Job.objects.get(pk=job_id)
        if job.pipeline_id:
            qs = qs.filter(
                detections__classifications__algorithm__in=job.pipeline.algorithms.all(),
                project_id=job.project_id,
            )

    return qs


def reconcile_missing_determinations(
    project_id: int | None = None,
    job_id: int | None = None,
    occurrence_ids: list[int] | None = None,
    dry_run: bool = True,
) -> IntegrityCheckResult:
    """Find occurrences missing determinations and repair them.

    Re-runs ``update_occurrence_determination`` on each affected row so the
    best available identification or prediction is promoted to the
    determination field. Occurrences that can't be resolved (e.g. no viable
    prediction) are counted as ``unfixable``.
    """
    from ami.main.models import Occurrence, update_occurrence_determination

    if occurrence_ids is not None:
        occurrences = Occurrence.objects.filter(
            pk__in=occurrence_ids,
            determination__isnull=True,
            detections__classifications__isnull=False,
        ).distinct()
    else:
        occurrences = get_occurrences_missing_determination(
            project_id=project_id,
            job_id=job_id,
        )

    result = IntegrityCheckResult(checked=occurrences.count())

    if result.checked == 0 or dry_run:
        return result

    logger.info("Found %d occurrences missing determination", result.checked)

    for occurrence in occurrences.iterator():
        try:
            updated = update_occurrence_determination(occurrence, current_determination=None, save=True)
            if updated:
                result.fixed += 1
            else:
                result.unfixable += 1
        except Exception:
            result.unfixable += 1
            logger.exception("Error reconciling occurrence %s", occurrence.pk)

    logger.info(
        "Integrity check reconciliation: %d fixed, %d unfixable out of %d checked",
        result.fixed,
        result.unfixable,
        result.checked,
    )
    return result
