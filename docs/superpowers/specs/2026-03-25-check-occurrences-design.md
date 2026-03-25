# Design: check_occurrences

## Problem

Occurrences can end up in inconsistent states through normal pipeline operation:
- Localization creates detections + occurrences, but classification may fail or never run, leaving occurrences with no determination
- Detections can become orphaned (no occurrence linked) if occurrence creation fails mid-pipeline
- Occurrences can become orphaned (no detections) if detections are deleted

There's no mechanism to detect or repair these issues. On the demo environment, 481 occurrences with null determinations crashed the frontend UI (which doesn't handle `determination: null`).

## Solution

A reusable `check_occurrences()` function in `ami/main/checks.py` that detects and optionally fixes data integrity issues. Callable from a management command (manual), a celery periodic task (automated monitoring), and potentially post-pipeline-save.

## Checks

### 1. Missing determination
**Query:** Occurrences where `determination IS NULL` but at least one detection has a classification.
```python
Occurrence.objects.filter(
    determination__isnull=True,
    detections__classifications__isnull=False
).distinct()
```
**Fix:** Call `update_occurrence_determination(occurrence, save=True)` for each.
**Severity:** Error — these should always have a determination.

### 2. Orphaned occurrences
**Query:** Occurrences with zero detections.
```python
Occurrence.objects.annotate(
    det_count=Count("detections")
).filter(det_count=0)
```
**Fix:** Delete the occurrence (no useful data without detections).
**Severity:** Warning — may be legitimate during pipeline processing.

### 3. Orphaned detections
**Query:** Detections where `occurrence IS NULL`.
```python
Detection.objects.filter(occurrence__isnull=True)
```
**Fix:** Log only. Re-linking requires pipeline context (which source image, event, etc). Could potentially call `create_and_update_occurrences_for_detections()` but that's a heavier operation best left to manual intervention.
**Severity:** Warning.

## API

### Core function

```python
# ami/main/checks.py

@dataclass
class OccurrenceCheckReport:
    missing_determination: list[int]   # occurrence PKs
    orphaned_occurrences: list[int]    # occurrence PKs (no detections)
    orphaned_detections: list[int]     # detection PKs (no occurrence)
    fixed_determinations: int          # count auto-fixed (when fix=True)
    deleted_occurrences: int           # count deleted (when fix=True)

    @property
    def has_issues(self) -> bool:
        return bool(
            self.missing_determination
            or self.orphaned_occurrences
            or self.orphaned_detections
        )

    @property
    def summary(self) -> str:
        """Human-readable one-line summary."""
        ...


def check_occurrences(
    project_id: int | None = None,
    fix: bool = False,
) -> OccurrenceCheckReport:
    """
    Check occurrence data integrity and optionally fix issues.

    Args:
        project_id: Scope to a single project. None = all projects.
        fix: If True, auto-fix what can be fixed (determinations, orphaned occurrences).
             If False (default), report only.

    Returns:
        OccurrenceCheckReport with findings and fix counts.
    """
```

### Management command

```
manage.py check_occurrences [--project-id N] [--fix]
```

Output format:
```
Checking occurrence integrity...
  Project: Vermont Atlas of Life (#5)

  Missing determination:  12 found, 12 fixed
  Orphaned occurrences:    3 found,  3 deleted
  Orphaned detections:     0 found

  Done. Fixed 15 issues.
```

Without `--fix`:
```
  Missing determination:  12 found
  Orphaned occurrences:    3 found
  Orphaned detections:     0 found

  Found 15 issues. Run with --fix to repair.
```

### Celery task

```python
# ami/main/tasks.py

@shared_task
def check_occurrences_task():
    """Periodic occurrence integrity check. Report-only, logs warnings."""
    report = check_occurrences(fix=False)
    if report.has_issues:
        logger.warning("Occurrence integrity issues found: %s", report.summary)
    return report.summary
```

Registered via django-celery-beat admin (IntervalSchedule or CrontabSchedule). Not hardcoded in beat config — the team can set frequency via admin. Suggested: daily.

## File locations

| Component | Path |
|-----------|------|
| Core function | `ami/main/checks.py` |
| Management command | `ami/main/management/commands/check_occurrences.py` |
| Celery task | `ami/main/tasks.py` (add to existing) |
| Tests | `ami/main/tests/test_checks.py` |

## Future considerations

- **Post-pipeline hook:** After `save_results()` completes, call `check_occurrences(project_id=job.project_id)` to catch issues immediately. Not in this PR — let's observe the patterns first via the periodic task.
- **Classification.save() signal:** Could trigger `update_occurrence_determination()` when classifications are added outside the pipeline path. Deferred — need to understand when this actually happens.
- **Metrics/alerting:** The periodic task could emit New Relic custom events or Sentry breadcrumbs for dashboarding. Deferred until we know the baseline.
