"""
Score occurrence tracking against the tracks people have confirmed in one project.

Ground truth is every occurrence whose grouping a person confirmed. Predictions come from
re-running the tracking link step over the raw detections of those sessions, as if none were
linked yet, with the tunables given here. Nothing is written: the command runs inside a
transaction that is always rolled back. See docs/claude/reference/tracking-evaluation.md.
"""

import json
import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ami.main.models import Detection, Event, Project
from ami.ml.post_processing.tracking_evaluation import TrackingEvaluation, evaluate_tracks, tracks_from_links
from ami.ml.post_processing.tracking_task import TrackingConfig, propose_event_links, resolve_feature_algorithm

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Score tracking against the confirmed tracks of a project, without writing anything."

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, required=True, help="Project ID.")
        parser.add_argument(
            "--event",
            type=int,
            action="append",
            dest="events",
            help="Session (event) ID to score; repeat for several. Default: every session with a confirmed track.",
        )
        defaults = TrackingConfig(event_ids=[0])
        parser.add_argument("--cost-threshold", type=float, default=defaults.cost_threshold)
        parser.add_argument("--require-features", dest="require_features", action="store_true")
        parser.add_argument("--no-require-features", dest="require_features", action="store_false")
        parser.set_defaults(require_features=defaults.require_features)
        parser.add_argument(
            "--feature-extraction-algorithm",
            type=int,
            default=None,
            help="Algorithm ID whose embeddings to compare. Default: the only one in the session.",
        )
        parser.add_argument("--format", choices=["text", "json"], default="text")
        parser.add_argument("--per-track", action="store_true", help="Include per-track scores in JSON output.")

    def handle(self, *args, **options):
        # Proposing links only reads, but the rollback guarantees a scoring run never changes data.
        with transaction.atomic():
            try:
                report = self._evaluate(options)
            finally:
                transaction.set_rollback(True)

        if options["format"] == "json":
            public = {key: value for key, value in report.items() if not key.startswith("_")}
            self.stdout.write(json.dumps(public, indent=2, default=str))
        else:
            self.stdout.write(self._as_text(report))

    def _evaluate(self, options) -> dict:
        project = Project.objects.filter(pk=options["project"]).first()
        if project is None:
            raise CommandError(f"Project {options['project']} not found.")

        detections = Detection.objects.valid().filter(
            source_image__project=project,
            occurrence__project=project,
            occurrence__grouping_verified_at__isnull=False,
        )
        if options["events"]:
            detections = detections.filter(source_image__event_id__in=options["events"])
        rows = list(detections.values_list("pk", "occurrence_id", "source_image__timestamp", "source_image__event_id"))

        event_ids = sorted({row[3] for row in rows if row[3] is not None})
        missing = sorted(set(options["events"] or []) - set(event_ids))
        if missing:
            logger.warning(f"No confirmed tracks in session(s) {missing} of project {project.pk}.")
        if not event_ids:
            raise CommandError(f"Project {project.pk} has no confirmed tracks in the sessions asked for.")

        config = TrackingConfig(
            event_ids=event_ids,
            cost_threshold=options["cost_threshold"],
            require_features=options["require_features"],
            feature_extraction_algorithm_id=options["feature_extraction_algorithm"],
        )

        ground_truth: dict[int, int] = {}
        timestamps: dict[int, object] = {}
        predictions: dict[int, int] = {}
        per_event: list[dict] = []
        skipped: list[dict] = []
        for event in Event.objects.filter(pk__in=event_ids).order_by("pk"):
            event_rows = [row for row in rows if row[3] == event.pk]
            algorithm, should_track, note = resolve_feature_algorithm(event, config)
            if not should_track:
                skipped.append({"event_id": event.pk, "reason": note, "confirmed_detections": len(event_rows)})
                continue

            links = propose_event_links(event, algorithm, config, logger)
            event_detection_ids = (
                Detection.objects.valid().filter(source_image__event=event).values_list("pk", flat=True)
            )
            event_predictions = tracks_from_links(event_detection_ids, [(a, b) for a, b, _ in links])
            event_truth = {pk: occurrence_id for pk, occurrence_id, _, _ in event_rows}
            event_times = {pk: timestamp for pk, _, timestamp, _ in event_rows}

            missing_times = sorted(pk for pk, timestamp in event_times.items() if timestamp is None)
            if missing_times:
                raise CommandError(
                    f"Session {event.pk} has {len(missing_times)} confirmed detection(s) on captures without "
                    f"a timestamp, e.g. detection {missing_times[:3]}; they cannot be put in capture order."
                )

            ground_truth.update(event_truth)
            timestamps.update(event_times)
            predictions.update(event_predictions)
            per_event.append(
                {
                    "event_id": event.pk,
                    "feature_extraction_algorithm_id": algorithm.pk if algorithm else None,
                    "note": note,
                    "links_proposed": len(links),
                    "evaluation": evaluate_tracks(event_truth, event_predictions, event_times),
                }
            )

        overall: TrackingEvaluation | None = None
        if ground_truth:
            overall = evaluate_tracks(ground_truth, predictions, timestamps)

        per_track = options["per_track"]
        return {
            "project_id": project.pk,
            "config": {
                "cost_threshold": config.cost_threshold,
                "require_features": config.require_features,
                "feature_extraction_algorithm_id": config.feature_extraction_algorithm_id,
            },
            "events": [
                {**entry, "evaluation": entry["evaluation"].to_dict(include_tracks=per_track)} for entry in per_event
            ],
            "skipped_events": skipped,
            "overall": overall.to_dict(include_tracks=per_track) if overall else None,
            "_overall_lines": overall.summary_lines() if overall else [],
            "_event_lines": {entry["event_id"]: entry["evaluation"].summary_lines() for entry in per_event},
        }

    def _as_text(self, report: dict) -> str:
        config = report["config"]
        lines = [
            f"Project {report['project_id']}: cost_threshold={config['cost_threshold']} "
            f"require_features={config['require_features']} "
            f"feature_extraction_algorithm_id={config['feature_extraction_algorithm_id']}",
        ]
        for entry in report["events"]:
            lines.append("")
            lines.append(f"Session {entry['event_id']} ({entry['links_proposed']} links proposed)")
            if entry["note"]:
                lines.append(f"  Note: {entry['note']}")
            lines.extend(f"  {line}" for line in report["_event_lines"][entry["event_id"]])
        for entry in report["skipped_events"]:
            lines.append("")
            lines.append(f"Session {entry['event_id']} skipped: {entry['reason']}")
        lines.append("")
        lines.append("Overall")
        lines.extend(f"  {line}" for line in report["_overall_lines"] or ["No session could be scored."])
        return "\n".join(lines)
