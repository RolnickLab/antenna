import logging
from dataclasses import dataclass, field

from django.db.models import Count

logger = logging.getLogger(__name__)


@dataclass
class OccurrenceCheckReport:
    missing_determination: list[int] = field(default_factory=list)
    orphaned_occurrences: list[int] = field(default_factory=list)
    orphaned_detections: list[int] = field(default_factory=list)
    fixed_determinations: int = 0
    deleted_occurrences: int = 0

    @property
    def has_issues(self) -> bool:
        return bool(self.missing_determination or self.orphaned_occurrences or self.orphaned_detections)

    @property
    def summary(self) -> str:
        parts = []
        if self.missing_determination:
            s = f"{len(self.missing_determination)} missing determination"
            if self.fixed_determinations:
                s += f" ({self.fixed_determinations} fixed)"
            parts.append(s)
        if self.orphaned_occurrences:
            s = f"{len(self.orphaned_occurrences)} orphaned occurrences"
            if self.deleted_occurrences:
                s += f" ({self.deleted_occurrences} deleted)"
            parts.append(s)
        if self.orphaned_detections:
            parts.append(f"{len(self.orphaned_detections)} orphaned detections")
        return ", ".join(parts) if parts else "No issues found"


def check_occurrences(
    project_id: int | None = None,
    fix: bool = False,
) -> OccurrenceCheckReport:
    """
    Check occurrence data integrity and optionally fix issues.

    Args:
        project_id: Scope to a single project. None = all projects.
        fix: If True, auto-fix what can be fixed. If False (default), report only.

    Returns:
        OccurrenceCheckReport with findings and fix counts.
    """
    from ami.main.models import Detection, Occurrence, update_occurrence_determination

    report = OccurrenceCheckReport()

    # Base querysets scoped by project
    occ_qs = Occurrence.objects.all()
    det_qs = Detection.objects.all()
    if project_id is not None:
        occ_qs = occ_qs.filter(project_id=project_id)
        det_qs = det_qs.filter(source_image__deployment__project_id=project_id)

    # Check 1: Missing determination
    # Occurrences with classifications but no determination set
    missing = occ_qs.filter(
        determination__isnull=True,
        detections__classifications__isnull=False,
    ).distinct()
    report.missing_determination = list(missing.values_list("pk", flat=True))

    if fix and report.missing_determination:
        for occ in missing.iterator():
            if update_occurrence_determination(occ, current_determination=None, save=True):
                report.fixed_determinations += 1
        logger.info(
            "Fixed %d/%d missing determinations",
            report.fixed_determinations,
            len(report.missing_determination),
        )

    # Check 2: Orphaned occurrences (no detections)
    orphaned_occ = occ_qs.annotate(det_count=Count("detections")).filter(det_count=0)
    report.orphaned_occurrences = list(orphaned_occ.values_list("pk", flat=True))

    if fix and report.orphaned_occurrences:
        deleted_count, _ = orphaned_occ.delete()
        report.deleted_occurrences = deleted_count
        logger.info("Deleted %d orphaned occurrences", deleted_count)

    # Check 3: Orphaned detections (no occurrence)
    orphaned_det = det_qs.filter(occurrence__isnull=True)
    report.orphaned_detections = list(orphaned_det.values_list("pk", flat=True))

    if report.orphaned_detections:
        logger.warning(
            "Found %d orphaned detections (no occurrence linked): %s",
            len(report.orphaned_detections),
            report.orphaned_detections[:10],
        )

    return report
