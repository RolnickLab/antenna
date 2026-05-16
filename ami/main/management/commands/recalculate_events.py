"""
Django management command to update existing events using improved clustering logic.

PURPOSE:
This command addresses data quality issues in existing event groupings by finding events
that are unusually long (indicating poor clustering) and recreating all events for those
deployments using the current, improved grouping algorithm.

BACKGROUND PROBLEMS:
The original event grouping logic had several issues:
1. Multiple events on the same day were grouped into a single event
2. Events spanning multiple days when they should be separate sessions

TYPICAL MONITORING PATTERNS:
Most camera trap deployments for nocturnal insects follow predictable patterns:
- Regular overnight sessions (evening to next morning) - these should span 2 calendar days
- Consistent start/end times within each deployment
- Occasional short daytime events for testing/maintenance
- Similar duration events within the same deployment

WHAT THIS COMMAND DOES:
1. Identifies deployments with unusually long events (default >8 hours)
2. Shows comprehensive before/after statistics for transparency
3. Recreates ALL events in those deployments using improved logic
4. Provides detailed analysis of changes including:
   - Event count and duration statistics
   - Multi-day events (spanning >2 calendar days)
   - Daily event distribution analysis
   - Outlier detection (events >2σ from mean duration)
   - Empty events that would be deleted

USE CASES:
- Audit existing data quality before making changes (--dry-run)
- Update problematic deployments after algorithm improvements
- Validate that event grouping matches expected monitoring schedules
- Identify deployments that may need manual review

SAFETY FEATURES:
- Dry-run mode shows all changes without applying them
- Project filtering to process specific datasets
- Comprehensive logging of all changes
- Before/after statistics for validation
"""

import logging
import statistics
import typing
from collections import defaultdict
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import models, transaction
from django.db.models import Count, Sum

from ...models import Deployment, Event, Project

logger = logging.getLogger(__name__)


def calculate_event_stats(events: list[Event]) -> dict[str, typing.Any]:
    """Calculate statistics for a list of events.

    Args:
        events: List of Event objects (already evaluated)

    Returns:
        Dictionary with event statistics
    """
    if not events:
        return {"count": 0}

    durations = []
    captures_counts = []
    daily_events = defaultdict(list)
    multi_day_events = []
    empty_events = []

    for event in events:
        if event.end and event.start:
            duration = event.end - event.start
            duration_hours = duration.total_seconds() / 3600
            durations.append(duration_hours)

            # Check for multi-day events (spanning MORE than 2 calendar days)
            # Normal overnight monitoring should span exactly 2 days (evening to next morning)
            days_spanned = (event.end.date() - event.start.date()).days + 1
            if days_spanned > 2:
                multi_day_events.append(event)

            # Group by date (using start date)
            daily_events[event.start.date()].append(event)

        captures_count = event.captures_count or 0
        captures_counts.append(captures_count)

        if captures_count == 0:
            empty_events.append(event)

    stats = {
        "count": len(events),
        "empty_events": empty_events,
        "multi_day_events": multi_day_events,
        "daily_events": daily_events,
    }

    if durations:
        stats.update(
            {
                "avg_duration_hours": statistics.mean(durations),
                "std_duration_hours": statistics.stdev(durations) if len(durations) > 1 else 0,
                "min_duration_hours": min(durations),
                "max_duration_hours": max(durations),
            }
        )

        # Find outliers (events more than 2 standard deviations from mean)
        if len(durations) > 2:
            mean_duration = stats["avg_duration_hours"]
            std_duration = stats["std_duration_hours"]
            outlier_threshold = 2 * std_duration
            outliers = []
            for i, event in enumerate(events):
                if event.end and event.start:
                    duration_hours = (event.end - event.start).total_seconds() / 3600
                    if abs(duration_hours - mean_duration) > outlier_threshold:
                        outliers.append(event)
            stats["outliers"] = outliers
        else:
            stats["outliers"] = []

    if captures_counts:
        stats.update(
            {
                "avg_captures": statistics.mean(captures_counts),
                "std_captures": statistics.stdev(captures_counts) if len(captures_counts) > 1 else 0,
                "min_captures": min(captures_counts),
                "max_captures": max(captures_counts),
            }
        )

    return stats


def format_stats_output(stats: dict[str, typing.Any], label: str) -> str:
    """Format statistics for display."""
    if not stats or stats["count"] == 0:
        return f"{label}: No events"

    lines = [f"{label}:"]
    lines.append(f"  Count: {stats['count']}")

    if "avg_duration_hours" in stats:
        lines.append(
            f"  Duration: avg={stats['avg_duration_hours']:.1f}h, "
            f"std={stats['std_duration_hours']:.1f}h, "
            f"range={stats['min_duration_hours']:.1f}h-{stats['max_duration_hours']:.1f}h"
        )

    if "avg_captures" in stats:
        lines.append(
            f"  Captures: avg={stats['avg_captures']:.0f}, "
            f"std={stats['std_captures']:.0f}, "
            f"range={stats['min_captures']}-{stats['max_captures']}"
        )

    if stats.get("empty_events"):
        lines.append(f"  Empty events (0 captures): {len(stats['empty_events'])}")

    if stats.get("multi_day_events"):
        lines.append(f"  Multi-day events (>2 days): {len(stats['multi_day_events'])}")

    if stats.get("outliers"):
        lines.append(f"  Outliers (>2σ from mean): {len(stats['outliers'])}")

    return "\n".join(lines)


class Command(BaseCommand):
    help = (
        "Update existing events using improved clustering logic. "
        "Finds deployments with unusually long events (indicating poor grouping) "
        "and recreates ALL events for those deployments. Provides comprehensive "
        "before/after analysis including statistics, outliers, and multi-day events. "
        "Use --dry-run to audit data quality without making changes."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--duration-hours",
            type=int,
            default=8,
            help="Minimum duration in hours for events to be considered for updating (default: 8)",
        )
        parser.add_argument(
            "--project",
            type=str,
            help="Filter to a specific project by ID",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without making any changes",
        )
        parser.add_argument(
            "--max-time-gap",
            type=int,
            default=120,
            help="Maximum time gap in minutes between images to group into the same event (default: 120)",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip confirmation prompt and proceed automatically",
        )

    def handle(self, *args: typing.Any, **options: typing.Any) -> None:
        duration_hours = options["duration_hours"]
        project_filter = options["project"]
        dry_run = options["dry_run"]
        max_time_gap_minutes = options["max_time_gap"]
        skip_confirmation = options["yes"]

        self.stdout.write(
            self.style.WARNING(f"{'DRY RUN: ' if dry_run else ''}Finding events longer than {duration_hours} hours...")
        )

        # Build the query for long events with optimized select_related
        long_events_query = (
            Event.objects.annotate(duration=models.F("end") - models.F("start"))
            .filter(duration__gte=timedelta(hours=duration_hours))
            .select_related("deployment", "deployment__project")
        )

        # Apply project filter if specified
        if project_filter:
            try:
                # Try to parse as ID first
                project_id = int(project_filter)
                project = Project.objects.get(pk=project_id)
            except (ValueError, Project.DoesNotExist):
                # Not an ID or doesn't exist, treat as name
                try:
                    project = Project.objects.get(name=project_filter)
                except Project.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"Project '{project_filter}' not found."))
                    return

            long_events_query = long_events_query.filter(deployment__project=project)
            self.stdout.write(f"Filtering to project: {project}")

        # Check count before evaluating queryset
        long_events_count = long_events_query.count()
        if long_events_count == 0:
            self.stdout.write("No events found matching the criteria.")
            return

        self.stdout.write(f"Found {long_events_count} events longer than {duration_hours} hours:")

        # Get deployments with long events using a more efficient approach
        # Now get the actual long events grouped by deployment
        long_events_by_deployment = defaultdict(list)
        for event in long_events_query:
            if event.deployment:  # Check if deployment exists
                long_events_by_deployment[event.deployment].append(event)

        self.stdout.write(f"\nThese events belong to {len(long_events_by_deployment)} deployment(s):")

        # Show before state - optimize to reduce queries
        total_events_before = 0
        total_captures_before = 0

        for deployment, long_events_list in long_events_by_deployment.items():
            self.stdout.write(f"\nDeployment: {deployment} ({deployment.project or 'No project'})")
            self.stdout.write(f"  Long events: {len(long_events_list)}")

            for event in long_events_list:
                # Calculate duration properly
                if event.end and event.start:
                    duration = event.end - event.start
                    duration_hours_actual = duration.total_seconds() / 3600
                else:
                    duration_hours_actual = 0

                self.stdout.write(
                    f"    - Event {event.pk}: {event.start} to {event.end} "
                    f"({duration_hours_actual:.1f} hours, {event.captures_count or 0} captures)"
                )

            # Get aggregated stats for this deployment in one query
            deployment_stats = Event.objects.filter(deployment=deployment).aggregate(
                event_count=Count("id"), total_captures=Sum("captures_count")
            )

            event_count = deployment_stats["event_count"] or 0
            captures_count = deployment_stats["total_captures"] or 0

            total_events_before += event_count
            total_captures_before += captures_count

            self.stdout.write(f"  Total events in deployment: {event_count}")
            self.stdout.write(f"  Total captures in deployment: {captures_count}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN: Analyzing what changes would be made..."))
            # Show detailed analysis for each deployment without making changes
            for deployment, long_events_list in long_events_by_deployment.items():
                self._analyze_deployment_preview(deployment, max_time_gap_minutes)

            self.stdout.write(
                self.style.WARNING("\nDRY RUN completed. Run without --dry-run to actually update events.")
            )
            return

        # Ask for user confirmation before proceeding
        if not skip_confirmation:
            self.stdout.write(
                self.style.WARNING(
                    f"\nAbout to process {len(long_events_by_deployment)} deployment(s). "
                    "This will recreate some events. Only empty events are deleted."
                )
            )

            confirm = input("Do you want to continue? [y/N]: ").lower().strip()
            if confirm not in ["y", "yes"]:
                self.stdout.write("Operation cancelled.")
                return
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\nProceeding automatically with {len(long_events_by_deployment)} deployment(s).")
            )

        # Process each deployment
        self.stdout.write(self.style.SUCCESS("\nProcessing deployments..."))

        total_events_after = 0
        total_captures_after = 0

        for deployment, long_events_list in long_events_by_deployment.items():
            with transaction.atomic():  # Wrap each deployment processing in a transaction
                events_after_count, captures_after_count = self._process_deployment(deployment, max_time_gap_minutes)
                total_events_after += events_after_count
                total_captures_after += captures_after_count

        # Summary
        self.stdout.write(self.style.SUCCESS("\nSummary:"))
        self.stdout.write(f"  Total events: {total_events_before} -> {total_events_after}")
        self.stdout.write(f"  Total captures: {total_captures_before} -> {total_captures_after}")

        events_diff = total_events_after - total_events_before
        if events_diff > 0:
            self.stdout.write(f"  Events created: +{events_diff}")
        elif events_diff < 0:
            self.stdout.write(f"  Events removed: {events_diff}")
        else:
            self.stdout.write("  Events count unchanged")

        self.stdout.write(self.style.SUCCESS("Event update completed!"))

    def _analyze_deployment_preview(self, deployment: Deployment, max_time_gap_minutes: int) -> None:
        """Analyze what changes would happen to a deployment without making them."""
        self.stdout.write(f"\n  Preview for deployment: {deployment}")

        # Get current stats using optimized queries
        events_current_qs = Event.objects.filter(deployment=deployment)

        current_stats = events_current_qs.aggregate(event_count=Count("id"), total_captures=Sum("captures_count"))

        events_current_count = current_stats["event_count"] or 0
        captures_current = current_stats["total_captures"] or 0

        self.stdout.write(f"    Current state: {events_current_count} events, {captures_current} captures")

        if events_current_count == 0:
            self.stdout.write("    No events to analyze.")
            return

        # Fetch events for detailed analysis
        events_current = list(events_current_qs)

        # Calculate current statistics for detailed analysis
        stats_current = calculate_event_stats(events_current)

        # Show current statistics
        self.stdout.write(f"    {format_stats_output(stats_current, 'Current Statistics')}")

        # Analyze current issues that would be fixed
        self._preview_current_issues(stats_current, max_time_gap_minutes)

        # Show what the analysis functions would report
        self.stdout.write("    Expected improvements after regrouping:")

        # Analyze multi-day events that would likely be split
        multi_day_current = stats_current.get("multi_day_events", [])
        if multi_day_current and isinstance(multi_day_current, list):
            self.stdout.write(f"      - Would likely split {len(multi_day_current)} multi-day events")
            for event in multi_day_current[:3]:  # Show first 3 as examples
                duration_hours = self._get_event_duration_hours(event)
                days_spanned = (event.end.date() - event.start.date()).days + 1 if event.end and event.start else 0
                self.stdout.write(f"        • Event {event.pk}: {duration_hours:.1f}h spanning {days_spanned} days")
            if len(multi_day_current) > 3:
                self.stdout.write(f"        • ... and {len(multi_day_current) - 3} more")

        # Analyze days with multiple events
        daily_events = stats_current.get("daily_events", {})
        if isinstance(daily_events, dict):
            days_with_multiple = {day: events for day, events in daily_events.items() if len(events) > 1}

            if days_with_multiple:
                self.stdout.write(f"      - Would analyze {len(days_with_multiple)} days with multiple events")
                for day, day_events in list(days_with_multiple.items())[:2]:  # Show first 2 as examples
                    self.stdout.write(f"        • {day}: {len(day_events)} events might be consolidated or split")
                if len(days_with_multiple) > 2:
                    self.stdout.write(f"        • ... and {len(days_with_multiple) - 2} more days")

        # Analyze outliers
        outliers = stats_current.get("outliers", [])
        if outliers and isinstance(outliers, list):
            self.stdout.write(f"      - Would address {len(outliers)} outlier events (>2σ from mean duration)")

        # Analyze empty events
        empty_events = stats_current.get("empty_events", [])
        if empty_events and isinstance(empty_events, list):
            self.stdout.write(f"      - Would remove {len(empty_events)} empty events (0 captures)")

        if not any(
            [
                multi_day_current and isinstance(multi_day_current, list),
                (
                    daily_events
                    and isinstance(daily_events, dict)
                    and any(len(events) > 1 for events in daily_events.values())
                ),
                outliers and isinstance(outliers, list),
                empty_events and isinstance(empty_events, list),
            ]
        ):
            self.stdout.write("      - No obvious improvements expected")

    def _preview_current_issues(self, stats_current: dict[str, typing.Any], max_time_gap_minutes: int) -> None:
        """Preview current issues that would be addressed by regrouping."""
        self.stdout.write("    Current issues that would be addressed:")

        issues_found = []

        # Check for multi-day events
        multi_day_events = stats_current.get("multi_day_events", [])
        if multi_day_events and isinstance(multi_day_events, list):
            issues_found.append(f"Multi-day events: {len(multi_day_events)} events span >2 calendar days")

        # Check for outlier durations
        outliers = stats_current.get("outliers", [])
        if outliers and isinstance(outliers, list):
            issues_found.append(f"Duration outliers: {len(outliers)} events >2σ from mean")

        # Check for empty events
        empty_events = stats_current.get("empty_events", [])
        if empty_events and isinstance(empty_events, list):
            issues_found.append(f"Empty events: {len(empty_events)} events with 0 captures")

        # Check for days with multiple events (potential over-splitting)
        daily_events = stats_current.get("daily_events", {})
        if isinstance(daily_events, dict):
            days_with_multiple = sum(1 for events in daily_events.values() if len(events) > 1)
            if days_with_multiple > 0:
                issues_found.append(f"Multiple events per day: {days_with_multiple} days with >1 event")

        # Check for very long events (the original criteria)
        if "avg_duration_hours" in stats_current:
            avg_duration = stats_current["avg_duration_hours"]
            max_duration = stats_current["max_duration_hours"]
            if max_duration > 12:  # Arbitrary threshold for "very long"
                issues_found.append(f"Very long events: max duration {max_duration:.1f}h (avg: {avg_duration:.1f}h)")

        if issues_found:
            for issue in issues_found:
                self.stdout.write(f"      • {issue}")
        else:
            self.stdout.write("      • No obvious issues detected")

        self.stdout.write(f"    Regrouping will use max time gap of {max_time_gap_minutes} minutes between captures")

    def _process_deployment(self, deployment: Deployment, max_time_gap_minutes: int) -> tuple[int, int]:
        """Process a single deployment, optimizing queryset usage.

        Returns:
            Tuple of (events_after_count, captures_after_count)
        """
        self.stdout.write(f"\nProcessing deployment: {deployment}")

        # Get before stats using optimized queries
        events_before_qs = Event.objects.filter(deployment=deployment)

        # Use aggregate to get counts efficiently
        before_stats = events_before_qs.aggregate(event_count=Count("id"), total_captures=Sum("captures_count"))

        events_before_count = before_stats["event_count"] or 0
        captures_before = before_stats["total_captures"] or 0

        # Only fetch events if we need detailed analysis
        events_before = list(events_before_qs) if events_before_count > 0 else []

        # Calculate before statistics
        stats_before = calculate_event_stats(events_before)

        # Store details of events before regrouping for comparison
        events_before_data = {}
        for event in events_before:
            events_before_data[event.pk] = {
                "start": event.start,
                "end": event.end,
                "captures_count": event.captures_count or 0,
            }

        # Dissociate all events in this deployment
        self.stdout.write("  Dissociating existing events...")
        # Create an EventQuerySet to access dissociate_related_objects method
        from ...models import EventQuerySet

        event_qs = EventQuerySet(Event, using="default").filter(deployment=deployment)
        event_qs.dissociate_related_objects()

        # Regroup images into events
        self.stdout.write(f"  Regrouping images (max gap: {max_time_gap_minutes} minutes)...")
        from ...models import group_images_into_events

        group_images_into_events(
            deployment=deployment,
            max_time_gap=timedelta(minutes=max_time_gap_minutes),
            use_existing=False,  # Regroup all images, not just new ones
        )

        # Get after stats using optimized queries
        events_after_qs = Event.objects.filter(deployment=deployment)

        after_stats = events_after_qs.aggregate(event_count=Count("id"), total_captures=Sum("captures_count"))

        events_after_count = after_stats["event_count"] or 0
        captures_after = after_stats["total_captures"] or 0

        # Only fetch events if we need detailed analysis
        events_after = list(events_after_qs) if events_after_count > 0 else []

        # Calculate after statistics
        stats_after = calculate_event_stats(events_after)

        self.stdout.write(f"  Events: {events_before_count} -> {events_after_count}")
        self.stdout.write(f"  Captures: {captures_before} -> {captures_after}")

        # Display statistics
        self.stdout.write(f"\n  {format_stats_output(stats_before, 'BEFORE Statistics')}")
        self.stdout.write(f"\n  {format_stats_output(stats_after, 'AFTER Statistics')}")

        # Categorize events as new, modified, or unchanged
        self._analyze_event_changes(events_before_data, events_after)

        # Analyze day-to-day date ranges with multiple events
        self._analyze_daily_events(stats_before, stats_after)

        # Analyze multi-day events that were split
        self._analyze_multi_day_events(stats_before, stats_after)

        return events_after_count, captures_after

    def _analyze_event_changes(
        self, events_before_data: dict[int, dict[str, typing.Any]], events_after: list[Event]
    ) -> None:
        """Analyze changes between before and after events."""
        new_events = []
        modified_events = []
        unchanged_events = []
        deleted_events = []

        # Find deleted events (events that existed before but not after)
        events_after_ids = {event.pk for event in events_after}
        for event_pk in events_before_data:
            if event_pk not in events_after_ids:
                # This event was deleted (probably had 0 captures)
                deleted_events.append(event_pk)

        for event in events_after:
            if event.pk in events_before_data:
                # Event existed before, check if it changed
                before_data = events_before_data[event.pk]
                if (
                    before_data["start"] != event.start
                    or before_data["end"] != event.end
                    or before_data["captures_count"] != (event.captures_count or 0)
                ):
                    modified_events.append(event)
                else:
                    unchanged_events.append(event)
            else:
                # This is a new event
                new_events.append(event)

        # Show details of truly new events
        if new_events:
            self.stdout.write(f"  New events ({len(new_events)}):")
            for event in new_events:
                duration_hours_actual = self._get_event_duration_hours(event)
                self.stdout.write(
                    f"    - Event {event.pk}: {event.start} to {event.end} "
                    f"({duration_hours_actual:.1f} hours, {event.captures_count or 0} captures)"
                )
        else:
            self.stdout.write("  New events: None")

        # Show details of modified events
        if modified_events:
            self.stdout.write(f"  Modified events ({len(modified_events)}):")
            for event in modified_events:
                before_data = events_before_data[event.pk]
                duration_hours_actual = self._get_event_duration_hours(event)
                self.stdout.write(
                    f"    - Event {event.pk}: {before_data['start']} to {before_data['end']} -> "
                    f"{event.start} to {event.end} "
                    f"({duration_hours_actual:.1f} hours, {event.captures_count or 0} captures)"
                )
        else:
            self.stdout.write("  Modified events: None")

        if unchanged_events:
            self.stdout.write(f"  Unchanged events: {len(unchanged_events)}")

        # Show deleted events (events with 0 captures that were removed)
        if deleted_events:
            self.stdout.write(f"  Deleted events (0 captures): {len(deleted_events)}")
            for event_pk in deleted_events:
                before_data = events_before_data[event_pk]
                self.stdout.write(
                    f"    - Event {event_pk}: {before_data['start']} to {before_data['end']} "
                    f"({before_data['captures_count']} captures) [DELETED]"
                )

    def _analyze_daily_events(self, stats_before: dict[str, typing.Any], stats_after: dict[str, typing.Any]) -> None:
        """Analyze daily event distribution."""
        self.stdout.write("\n  Day-to-day analysis:")
        after_daily_events = stats_after.get("daily_events", {})
        before_daily_events = stats_before.get("daily_events", {})

        days_with_multiple_events_after = {
            day: events for day, events in after_daily_events.items() if len(events) > 1
        }
        days_with_multiple_events_before = {
            day: events for day, events in before_daily_events.items() if len(events) > 1
        }

        if days_with_multiple_events_after:
            count = len(days_with_multiple_events_after)
            self.stdout.write(f"    Days with multiple events AFTER regrouping: {count}")
            for day, day_events in sorted(days_with_multiple_events_after.items()):
                self.stdout.write(f"      {day}: {len(day_events)} events")
                for event in day_events:
                    duration_hours = self._get_event_duration_hours(event)
                    self.stdout.write(
                        f"        - {event.start.strftime('%H:%M')} to {event.end.strftime('%H:%M')} "
                        f"({duration_hours:.1f}h, {event.captures_count or 0} captures)"
                    )
        else:
            self.stdout.write("    No days with multiple events after regrouping")

        if days_with_multiple_events_before:
            count = len(days_with_multiple_events_before)
            self.stdout.write(f"    Days with multiple events BEFORE regrouping: {count}")

    def _analyze_multi_day_events(
        self, stats_before: dict[str, typing.Any], stats_after: dict[str, typing.Any]
    ) -> None:
        """Analyze multi-day events that were split."""
        self.stdout.write("\n  Multi-day event analysis:")
        self.stdout.write("    (Multi-day = spanning MORE than 2 calendar days)")
        self.stdout.write("    (Normal overnight monitoring spans exactly 2 days)")
        multi_day_before = stats_before.get("multi_day_events", [])
        multi_day_after = stats_after.get("multi_day_events", [])

        if multi_day_before:
            self.stdout.write(f"    Multi-day events BEFORE: {len(multi_day_before)}")
            for event in multi_day_before:
                duration_hours = self._get_event_duration_hours(event)
                if event.end and event.start:
                    days_spanned = (event.end.date() - event.start.date()).days + 1
                else:
                    days_spanned = 0
                self.stdout.write(
                    f"      - Event {event.pk}: {event.start.strftime('%Y-%m-%d %H:%M')} to "
                    f"{event.end.strftime('%Y-%m-%d %H:%M')} ({duration_hours:.1f}h, {days_spanned} days)"
                )

        if multi_day_after:
            self.stdout.write(f"    Multi-day events AFTER: {len(multi_day_after)}")
            for event in multi_day_after:
                duration_hours = self._get_event_duration_hours(event)
                if event.end and event.start:
                    days_spanned = (event.end.date() - event.start.date()).days + 1
                else:
                    days_spanned = 0
                self.stdout.write(
                    f"      - Event {event.pk}: {event.start.strftime('%Y-%m-%d %H:%M')} to "
                    f"{event.end.strftime('%Y-%m-%d %H:%M')} ({duration_hours:.1f}h, {days_spanned} days)"
                )

        if len(multi_day_before) > len(multi_day_after):
            self.stdout.write(f"    ✓ Reduced multi-day events from {len(multi_day_before)} to {len(multi_day_after)}")

    def _get_event_duration_hours(self, event: Event) -> float:
        """Calculate event duration in hours."""
        if event.end and event.start:
            duration = event.end - event.start
            return duration.total_seconds() / 3600
        return 0
