"""
Data integrity checks for the main app.

Functions here can be called from management commands, post-job hooks,
or periodic Celery tasks.
"""

import dataclasses
import logging

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ReconcileResult:
    checked: int = 0
    fixed: int = 0
    unfixable: int = 0


def get_occurrences_missing_determination(
    project_id: int | None = None,
    job_id: int | None = None,
):
    """
    Return occurrences that have detections with classifications but no determination set.

    Occurrences with no classifications at all are excluded (they legitimately have no
    determination).
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
        if job.pipeline:
            qs = qs.filter(
                detections__classifications__algorithm__in=job.pipeline.algorithms.all(),
                project_id=job.project_id,
            )

    return qs


def reconcile_missing_determinations(
    project_id: int | None = None,
    job_id: int | None = None,
    occurrence_ids: list[int] | None = None,
    dry_run: bool = False,
) -> ReconcileResult:
    """
    Find occurrences missing determinations and attempt to fix them by re-running
    update_occurrence_determination.
    """
    from ami.main.models import update_occurrence_determination

    if occurrence_ids is not None:
        from ami.main.models import Occurrence

        occurrences = (
            Occurrence.objects.filter(
                pk__in=occurrence_ids,
                determination__isnull=True,
                detections__classifications__isnull=False,
            )
            .distinct()
            .select_related("determination")
        )
    else:
        occurrences = get_occurrences_missing_determination(
            project_id=project_id,
            job_id=job_id,
        ).select_related("determination")

    result = ReconcileResult(checked=occurrences.count())

    if result.checked == 0 or dry_run:
        return result

    logger.info(f"Found {result.checked} occurrences missing determination")

    for occurrence in occurrences.iterator():
        try:
            updated = update_occurrence_determination(occurrence, current_determination=None, save=True)
            if updated:
                result.fixed += 1
            else:
                result.unfixable += 1
        except Exception:
            result.unfixable += 1
            logger.exception(f"Error reconciling occurrence {occurrence.pk}")

    logger.info(
        f"Reconciliation complete: {result.fixed} fixed, {result.unfixable} unfixable "
        f"out of {result.checked} checked"
    )
    return result
