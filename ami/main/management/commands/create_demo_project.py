import json
import pathlib
import time

from django.core.management.base import BaseCommand

from ami.main.models import Deployment, Detection, Device, Event, Occurrence, Project, SourceImage, TaxaList, Taxon
from ami.ml.models import Algorithm, Pipeline
from ami.tests.fixtures.main import create_complete_test_project, create_local_admin_user
from ami.tests.fixtures.tracking import DEFAULT_MOTION_SCALE, DEFAULT_SEED, TrackingSessionGroundTruth


class Command(BaseCommand):
    r"""Create example data needed for development and tests."""

    help = "Create example data needed for development and tests"

    def add_arguments(self, parser):
        # Add option to delete existing data
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete existing data before creating new demo project",
        )
        parser.add_argument(
            "--no-tracking-session",
            action="store_false",
            dest="tracking_session",
            help="Skip the extra capture session built for occurrence tracking",
        )
        parser.add_argument(
            "--tracking-frames",
            type=int,
            default=24,
            help="Number of consecutive captures in the tracking session (default: 24)",
        )
        parser.add_argument(
            "--tracking-interval-minutes",
            type=int,
            default=2,
            help="Minutes between captures in the tracking session (default: 2)",
        )
        parser.add_argument(
            "--tracking-motion-scale",
            type=float,
            default=DEFAULT_MOTION_SCALE,
            help=(
                "How far a simulated insect drifts between captures. Raise it above the default of "
                f"{DEFAULT_MOTION_SCALE} to make the session harder to track"
            ),
        )
        parser.add_argument(
            "--no-features",
            action="store_false",
            dest="with_features",
            help="Skip the synthetic feature embeddings, leaving tracking to match on geometry alone",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=DEFAULT_SEED,
            help=f"Random seed for the tracking session (default: {DEFAULT_SEED})",
        )
        parser.add_argument(
            "--ground-truth-output",
            type=str,
            default=None,
            help="Write the tracking session's ground-truth grouping to this JSON file",
        )

    def handle(self, *args, **options):
        if options["delete"]:
            self.stdout.write(self.style.WARNING("! Deleting existing data !"))
            time.sleep(2)
            for model in [
                Project,
                Device,
                Deployment,
                TaxaList,
                Taxon,
                Event,
                SourceImage,
                Detection,
                Occurrence,
                Algorithm,
                Pipeline,
            ]:
                self.stdout.write(f"Deleting all {model._meta.verbose_name_plural} and related objects")
                model.objects.all().delete()

        self.stdout.write("Creating test project")
        create_local_admin_user()
        tracking_kwargs = {}
        if options["tracking_session"]:
            tracking_kwargs = dict(
                num_frames=options["tracking_frames"],
                minutes_interval=options["tracking_interval_minutes"],
                motion_scale=options["tracking_motion_scale"],
                with_features=options["with_features"],
                seed=options["seed"],
            )
        project, ground_truth = create_complete_test_project(
            with_tracking_session=options["tracking_session"], **tracking_kwargs
        )
        self.stdout.write(self.style.SUCCESS(f"Created project #{project.pk} {project.name}"))

        if ground_truth:
            self.report_tracking_session(ground_truth)
            if options["ground_truth_output"]:
                path = pathlib.Path(options["ground_truth_output"])
                path.write_text(json.dumps(ground_truth.as_dict(), indent=2))
                self.stdout.write(f"Wrote the full detection-to-insect mapping to {path}")

    def report_tracking_session(self, ground_truth: TrackingSessionGroundTruth) -> None:
        """Print what a tracking run over this session is expected to find."""
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Tracking session"))
        self.stdout.write(f"  Event:       {ground_truth.event_id}")
        self.stdout.write(f"  Capture set: {ground_truth.capture_set_id}")
        self.stdout.write(f"  Captures:    {ground_truth.capture_count}")
        self.stdout.write(
            f"  Detections:  {ground_truth.detection_count}, one occurrence each, the way a pipeline leaves them"
        )
        self.stdout.write(f"  Seed:        {ground_truth.seed}")
        if ground_truth.feature_algorithm_key:
            self.stdout.write(f"  Embeddings:  from algorithm '{ground_truth.feature_algorithm_key}'")
        else:
            self.stdout.write("  Embeddings:  none, so track with require_features=False")
        self.stdout.write("")
        self.stdout.write("  Simulated insect  Species                Frames     Detections")
        for insect in ground_truth.insects:
            frames = f"{min(insect.frame_numbers)}-{max(insect.frame_numbers)}"
            self.stdout.write(
                f"  {insect.identifier:<17} {insect.taxon_name:<22} {frames:<10} {len(insect.detection_ids)}"
            )
        self.stdout.write("")
        self.stdout.write(
            f"  A perfect run leaves {len(ground_truth.insects)} occurrences, the longest spanning "
            f"{ground_truth.chain_lengths[0]} detections."
        )
