"""
Score occurrence tracking against the tracks people have confirmed in one project.

Ground truth is every occurrence whose grouping a person confirmed. Predictions come from
re-running the tracking link step over the raw detections of those sessions, as if none were
linked yet, with the tunables given here. ``--sweep`` scores many settings in one run. Nothing
is written: the command runs inside a transaction that is always rolled back. See
docs/claude/reference/tracking-evaluation.md.
"""

import csv
import itertools
import json
import logging
import pathlib

import numpy as np
import pydantic
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ami.main.models import Detection, Event, Project
from ami.ml.post_processing.tracking_evaluation import (
    TrackingEvaluation,
    evaluate_tracks,
    format_sweep_markdown,
    summarise_session,
    sweep_row,
    tracks_from_links,
)
from ami.ml.post_processing.tracking_task import (
    TrackingConfig,
    event_transition_pairs,
    links_from_transition_pairs,
    resolve_feature_algorithm,
    top_labels,
)

logger = logging.getLogger(__name__)

# Fields that name the sessions to track; the command sets them itself.
SCOPE_FIELDS = {"event_ids", "source_image_collection_id"}
# Guards that decide whether a run writes, not how it links; scoring ignores them.
WRITE_GUARD_FIELDS = {"skip_if_human_identifications", "require_completely_processed_session", "require_fresh_event"}


def _json_argument(value: str):
    """Inline JSON, or the path of a file holding it."""
    text = value
    if not value.lstrip().startswith(("{", "[")):
        path = pathlib.Path(value)
        if not path.is_file():
            raise CommandError(f"Not JSON and not a file: {value[:80]}")
        text = path.read_text()
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise CommandError(f"Not valid JSON: {value[:80]} ({error})")


def expand_sweep(spec) -> list[dict]:
    """The settings a sweep runs, in order.

    ``spec`` is a list of settings, or ``{"base": {...}, "grid": {field: [values]}, "configs": [...]}``:
    every combination of the grid values, each on top of ``base``, followed by each entry of
    ``configs`` on top of ``base``. A grid value that is an object is merged in whole, so one
    grid axis can set several fields together (for example a gate mode and its penalty).
    """
    if isinstance(spec, list):
        spec = {"configs": spec}
    if not isinstance(spec, dict):
        raise CommandError("A sweep is a list of settings or an object with base, grid and configs.")
    unknown = set(spec) - {"base", "grid", "configs"}
    if unknown:
        raise CommandError(f"Unknown sweep keys: {sorted(unknown)}")
    base = spec.get("base") or {}
    grid = spec.get("grid") or {}
    settings = []
    if grid:
        names = list(grid)
        for values in itertools.product(*(grid[name] for name in names)):
            setting = dict(base)
            for name, value in zip(names, values):
                setting.update(value if isinstance(value, dict) else {name: value})
            settings.append(setting)
    settings.extend({**base, **extra} for extra in spec.get("configs") or [])
    if not settings:
        raise CommandError("The sweep names no settings.")
    return settings


def load_vectors_file(path: str) -> dict[int, np.ndarray]:
    """Embeddings from an ``.npz`` file with arrays ``detection_ids`` (n) and ``vectors`` (n x d)."""
    try:
        with np.load(path) as data:
            ids, vectors = data["detection_ids"], data["vectors"]
    except (OSError, KeyError, ValueError) as error:
        raise CommandError(f"Cannot read vectors from {path}: {error}")
    if len(ids) != len(vectors):
        raise CommandError(f"{path}: {len(ids)} detection ids but {len(vectors)} vectors")
    return {int(detection_id): vector for detection_id, vector in zip(ids, vectors)}


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
        parser.add_argument(
            "--config",
            default=None,
            help='JSON object (inline or a file) of further TrackingConfig settings, e.g. \'{"species_gate": '
            '"forbid"}\'. Overrides the options above.',
        )
        parser.add_argument(
            "--sweep",
            default=None,
            help="JSON (inline or a file): a list of settings, or {base, grid, configs}. Scores each setting.",
        )
        parser.add_argument(
            "--vectors-file",
            default=None,
            help="An .npz of detection_ids and vectors to compare instead of the stored embeddings.",
        )
        parser.add_argument("--output-dir", default=None, help="With --sweep, write sweep.json and sweep.md here.")
        parser.add_argument("--per-track-csv", default=None, help="Write one row per scored track to this file.")
        parser.add_argument("--format", choices=["text", "json"], default="text")
        parser.add_argument("--per-track", action="store_true", help="Include per-track scores in JSON output.")

    def handle(self, *args, **options):
        base = {
            "cost_threshold": options["cost_threshold"],
            "require_features": options["require_features"],
            "feature_extraction_algorithm_id": options["feature_extraction_algorithm"],
        }
        if options["config"]:
            extra = _json_argument(options["config"])
            if not isinstance(extra, dict):
                raise CommandError("--config takes a JSON object.")
            base.update(extra)
        settings = [base]
        if options["sweep"]:
            settings = [{**base, **setting} for setting in expand_sweep(_json_argument(options["sweep"]))]
        for setting in settings:
            scope = SCOPE_FIELDS & set(setting)
            if scope:
                raise CommandError(f"The command chooses the sessions; remove {sorted(scope)} from the settings.")
        vectors = load_vectors_file(options["vectors_file"]) if options["vectors_file"] else None

        # Proposing links only reads, but the rollback guarantees a scoring run never changes data.
        with transaction.atomic():
            try:
                reports = self._evaluate(options, settings, vectors)
            finally:
                transaction.set_rollback(True)

        if options["per_track_csv"]:
            self._write_per_track_csv(options["per_track_csv"], reports)

        if options["sweep"]:
            self._write_sweep(options, settings, reports)
            return

        (report,) = reports
        if options["format"] == "json":
            self.stdout.write(json.dumps(self._public(report, options["per_track"]), indent=2, default=str))
        else:
            self.stdout.write(self._as_text(report))

    def _evaluate(self, options, settings: list[dict], vectors) -> list[dict]:
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
        rows = list(
            detections.values_list(
                "pk",
                "occurrence_id",
                "source_image__timestamp",
                "source_image__event_id",
                "occurrence__determination_id",
            )
        )

        event_ids = sorted({row[3] for row in rows if row[3] is not None})
        missing = sorted(set(options["events"] or []) - set(event_ids))
        if missing:
            logger.warning(f"No confirmed tracks in session(s) {missing} of project {project.pk}.")
        if not event_ids:
            raise CommandError(f"Project {project.pk} has no confirmed tracks in the sessions asked for.")

        configs = []
        for setting in settings:
            try:
                configs.append(TrackingConfig(event_ids=event_ids, **setting))
            except pydantic.ValidationError as error:
                raise CommandError(f"Invalid tracking settings {setting}: {error}")

        events = list(Event.objects.filter(pk__in=event_ids).order_by("pk"))
        truth_by_event: dict[int, dict] = {}
        for event in events:
            event_rows = [row for row in rows if row[3] == event.pk]
            missing_times = sorted(row[0] for row in event_rows if row[2] is None)
            if missing_times:
                raise CommandError(
                    f"Session {event.pk} has {len(missing_times)} confirmed detection(s) on captures without "
                    f"a timestamp, e.g. detection {missing_times[:3]}; they cannot be put in capture order."
                )
            truth_by_event[event.pk] = {
                "truth": {pk: occurrence_id for pk, occurrence_id, _, _, _ in event_rows},
                "times": {pk: timestamp for pk, _, timestamp, _, _ in event_rows},
                "taxa": {occurrence_id: taxon_id for _, occurrence_id, _, _, taxon_id in event_rows},
            }

        # Reading and scoring the pairs is the slow part, and it is the same for every setting
        # that compares the same embeddings, so it is done once per session and extractor.
        pairs_cache: dict[tuple, tuple] = {}
        labels_cache: dict[int, dict] = {}
        reports = []
        for index, config in enumerate(configs):
            if len(configs) > 1:
                logger.info(f"Scoring setting {index + 1}/{len(configs)}: {settings[index]}")
            reports.append(
                self._evaluate_config(project, events, config, truth_by_event, vectors, pairs_cache, labels_cache)
            )
        return reports

    def _evaluate_config(self, project, events, config, truth_by_event, vectors, pairs_cache, labels_cache) -> dict:
        ground_truth: dict[int, int] = {}
        timestamps: dict[int, object] = {}
        taxa: dict[int, object] = {}
        predictions: dict[int, int] = {}
        all_labels: dict[int, tuple] = {}
        per_event: list[dict] = []
        skipped: list[dict] = []
        for event in events:
            truth = truth_by_event[event.pk]
            if vectors is not None:
                algorithm, should_track, note = None, True, "Embeddings from the vectors file."
            else:
                algorithm, should_track, note = resolve_feature_algorithm(event, config)
            if not should_track:
                skipped.append({"event_id": event.pk, "reason": note, "confirmed_detections": len(truth["truth"])})
                continue

            key = (event.pk, algorithm.pk if algorithm else None)
            if key not in pairs_cache:
                pairs_cache[key] = event_transition_pairs(event, algorithm, vectors)
            transitions, event_detection_ids = pairs_cache[key]
            if event.pk not in labels_cache:
                labels_cache[event.pk] = top_labels(event_detection_ids)
            labels = labels_cache[event.pk]

            links = links_from_transition_pairs(transitions, config, labels)
            event_predictions = tracks_from_links(event_detection_ids, [(a, b) for a, b, _ in links])
            session_labels = {pk: (label.taxon_id, label.score) for pk, label in labels.items()}

            ground_truth.update(truth["truth"])
            timestamps.update(truth["times"])
            taxa.update(truth["taxa"])
            predictions.update(event_predictions)
            all_labels.update(session_labels)
            per_event.append(
                {
                    "event_id": event.pk,
                    "feature_extraction_algorithm_id": algorithm.pk if algorithm else None,
                    "note": note,
                    "links_proposed": len(links),
                    "evaluation": evaluate_tracks(truth["truth"], event_predictions, truth["times"], truth["taxa"]),
                    "session": summarise_session(event_predictions, session_labels),
                }
            )

        overall: TrackingEvaluation | None = None
        if ground_truth:
            overall = evaluate_tracks(ground_truth, predictions, timestamps, taxa)
        return {
            "project_id": project.pk,
            "config": {
                key: value
                for key, value in config.dict().items()
                if key not in SCOPE_FIELDS and key not in WRITE_GUARD_FIELDS
            },
            "events": per_event,
            "skipped_events": skipped,
            "overall": overall,
            "overall_session": summarise_session(predictions, all_labels) if predictions else None,
            "links_proposed": sum(entry["links_proposed"] for entry in per_event),
        }

    @staticmethod
    def _public(report: dict, per_track: bool) -> dict:
        overall = report["overall"]
        return {
            "project_id": report["project_id"],
            "config": report["config"],
            "events": [
                {**entry, "evaluation": entry["evaluation"].to_dict(include_tracks=per_track)}
                for entry in report["events"]
            ],
            "skipped_events": report["skipped_events"],
            "overall": overall.to_dict(include_tracks=per_track) if overall else None,
            "overall_session": report["overall_session"],
        }

    def _write_sweep(self, options, settings: list[dict], reports: list[dict]) -> None:
        rows = []
        for index, (setting, report) in enumerate(zip(settings, reports), start=1):
            for entry in report["events"]:
                rows.append(
                    sweep_row(
                        index,
                        setting,
                        entry["event_id"],
                        entry["evaluation"],
                        entry["session"],
                        entry["links_proposed"],
                    )
                )
            if report["overall"] is not None:
                rows.append(
                    sweep_row(
                        index,
                        setting,
                        "overall",
                        report["overall"],
                        report["overall_session"],
                        report["links_proposed"],
                    )
                )
        document = {
            "project_id": options["project"],
            "vectors_file": bool(options["vectors_file"]),
            "runs": [
                {"index": index, "settings": setting, **self._public(report, options["per_track"])}
                for index, (setting, report) in enumerate(zip(settings, reports), start=1)
            ],
            "rows": rows,
        }
        markdown = format_sweep_markdown(rows)
        if options["output_dir"]:
            directory = pathlib.Path(options["output_dir"])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "sweep.json").write_text(json.dumps(document, indent=2, default=str))
            (directory / "sweep.md").write_text(markdown)
        if options["format"] == "json":
            self.stdout.write(json.dumps(document, indent=2, default=str))
        else:
            self.stdout.write(markdown)

    @staticmethod
    def _write_per_track_csv(path: str, reports: list[dict]) -> None:
        fields = [
            "run",
            "event_id",
            "kind",
            "track_id",
            "length",
            "fragments",
            "completeness",
            "exactly_recovered",
            "ground_truth_tracks",
            "purity",
        ]
        with open(path, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for run, report in enumerate(reports, start=1):
                for entry in report["events"]:
                    evaluation = entry["evaluation"]
                    for score in evaluation.ground_truth_track_scores:
                        writer.writerow(
                            {
                                "run": run,
                                "event_id": entry["event_id"],
                                "kind": "confirmed",
                                "track_id": score.track_id,
                                "length": score.length,
                                "fragments": score.fragments,
                                "completeness": round(score.completeness, 4),
                                "exactly_recovered": score.exactly_recovered,
                            }
                        )
                    for score in evaluation.predicted_track_scores:
                        writer.writerow(
                            {
                                "run": run,
                                "event_id": entry["event_id"],
                                "kind": "predicted",
                                "track_id": score.first_detection_id,
                                "length": score.length,
                                "ground_truth_tracks": score.ground_truth_tracks,
                                "purity": round(score.purity, 4),
                            }
                        )

    def _as_text(self, report: dict) -> str:
        config = report["config"]
        changed = {
            key: value
            for key, value in config.items()
            if key not in {"cost_threshold", "require_features", "feature_extraction_algorithm_id"}
            and value != TrackingConfig.__fields__[key].default
        }
        lines = [
            f"Project {report['project_id']}: cost_threshold={config['cost_threshold']} "
            f"require_features={config['require_features']} "
            f"feature_extraction_algorithm_id={config['feature_extraction_algorithm_id']}"
            + (f" {changed}" if changed else ""),
        ]
        for entry in report["events"]:
            lines.append("")
            lines.append(f"Session {entry['event_id']} ({entry['links_proposed']} links proposed)")
            if entry["note"]:
                lines.append(f"  Note: {entry['note']}")
            lines.extend(f"  {line}" for line in entry["evaluation"].summary_lines())
        for entry in report["skipped_events"]:
            lines.append("")
            lines.append(f"Session {entry['event_id']} skipped: {entry['reason']}")
        lines.append("")
        lines.append("Overall")
        overall = report["overall"]
        lines.extend(f"  {line}" for line in (overall.summary_lines() if overall else ["No session could be scored."]))
        return "\n".join(lines)
