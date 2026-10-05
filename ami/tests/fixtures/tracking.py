"""A synthetic capture session that occurrence tracking can actually group.

Tracking links detections in *consecutive* captures, so data that scatters detections
across non-adjacent captures produces no links at all. What this module generates is one
long run of closely-spaced captures in which each simulated insect holds still enough for
its bounding boxes to overlap frame to frame, alongside the ground-truth grouping a
tracking run can be scored against.

The session is left the way a real pipeline leaves a session: one occurrence per
detection, no ``next_detection`` links. That is what ``event_is_fresh()`` expects.
"""

import dataclasses
import datetime
import io
import logging
import pathlib
import random

import numpy as np
from django.db import connection, models

from ami.main.models import (
    Classification,
    Deployment,
    Detection,
    Event,
    Occurrence,
    SourceImage,
    SourceImageCollection,
    TaxaList,
    Taxon,
    TaxonRank,
    group_images_into_events,
)
from ami.ml.models.algorithm import Algorithm
from ami.ml.tasks import create_detection_images
from ami.tests.fixtures.images import generate_moth_series
from ami.utils import s3

logger = logging.getLogger(__name__)

DEFAULT_SEED = 20260902

# One algorithm stands in for the classifier that would have produced both the species
# label and the backbone embedding. Tracking infers its feature extractor from the
# classifications on an event, and refuses to guess when more than one produced features.
DEMO_CLASSIFIER_KEY = "demo-tracking-classifier"
DEMO_CLASSIFIER_NAME = "Demo Tracking Classifier"

# Measured at these defaults: an insect's own consecutive detections score under 0.15 on the
# geometry-only matching cost, and two different insects never score below 1.2. Raise the
# scale to make the session harder to track; larger moths tolerate drift better.
DEFAULT_MOTION_SCALE = 0.2
TRACKING_MOTH_SIZE_RANGE = (50, 90)


@dataclasses.dataclass
class SimulatedInsect:
    """One simulated insect: the detections a perfect tracking run would group together."""

    identifier: str
    taxon_name: str
    frame_numbers: list[int]
    detection_ids: list[int]


@dataclasses.dataclass
class TrackingSessionGroundTruth:
    """Everything needed to score a tracking run over the generated session."""

    project_id: int
    deployment_id: int
    event_id: int
    capture_set_id: int
    seed: int
    capture_count: int
    detection_count: int
    feature_algorithm_key: str | None
    insects: list[SimulatedInsect]

    @property
    def chain_lengths(self) -> list[int]:
        return sorted((len(insect.detection_ids) for insect in self.insects), reverse=True)

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def pgvector_is_available() -> bool:
    """Can this database store ``Classification.features_2048``?"""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        return cursor.fetchone() is not None


def _session_start_timestamp(deployment: Deployment) -> datetime.datetime:
    """Pick a night of its own for the tracking session.

    Captures group into events by time, so starting a week before anything else in the
    deployment keeps the session in an event nobody else shares. Naive local time,
    because ``USE_TZ`` is off and capture timestamps are deployment-local.
    """
    earliest = SourceImage.objects.filter(deployment=deployment).aggregate(models.Min("timestamp"))["timestamp__min"]
    if earliest:
        return earliest - datetime.timedelta(days=7)
    return (datetime.datetime.now() - datetime.timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)


def _species_taxa(project, taxa_list: TaxaList | None) -> list[Taxon]:
    taxa_qs = taxa_list.taxa if taxa_list else Taxon.objects.filter(projects=project)
    species = list(taxa_qs.filter(rank=TaxonRank.SPECIES.name).order_by("name"))
    if not species:
        raise ValueError("No species-rank taxa available to classify the simulated insects with.")
    return species


def _upload_frames(deployment: Deployment, frames) -> None:
    if deployment.data_source is None:
        raise ValueError(f"Deployment {deployment.pk} has no data source to upload generated captures to.")
    config = deployment.data_source.config
    subdir = f"deployment_{deployment.pk}"
    for frame in frames:
        buffer = io.BytesIO()
        frame.image.save(buffer, format="JPEG")
        key = f"{subdir}/{frame.filename}"
        s3.write_file(config, key, buffer.getvalue())
        frame.object_store_key = key
    logger.info(f"Uploaded {len(frames)} tracking frames to {config.bucket_name}/{subdir}")


def _captures_for_frames(deployment: Deployment, frames) -> list[SourceImage]:
    """Return the imported captures for ``frames``, in frame order."""
    filenames = [frame.filename for frame in frames]
    by_filename = {
        pathlib.Path(image.path).name: image
        for image in SourceImage.objects.filter(deployment=deployment)
        if image.path
    }
    missing = [name for name in filenames if name not in by_filename]
    if missing:
        raise RuntimeError(f"{len(missing)} generated frame(s) were not imported by sync_captures: {missing[:3]}")
    return [by_filename[name] for name in filenames]


def create_tracking_session(
    deployment: Deployment,
    taxa_list: TaxaList | None = None,
    num_frames: int = 24,
    minutes_interval: int = 2,
    num_moths: int = 6,
    num_transient_moths: int = 4,
    min_frames_per_moth: int = 6,
    motion_scale: float = DEFAULT_MOTION_SCALE,
    with_features: bool = True,
    create_crops: bool = True,
    seed: int = DEFAULT_SEED,
) -> TrackingSessionGroundTruth:
    """
    Add one trackable capture session to ``deployment`` and return its ground truth.

    ``num_moths`` insects each stay for a run of at least ``min_frames_per_moth`` captures,
    which is what gives tracking real chains to rebuild; ``num_transient_moths`` appear in a
    single frame each, which is what gives it singletons it must leave alone.

    The same ``seed`` reproduces the same positions, lifespans, species and scores; it is set
    on the global ``random`` module, so it also affects whatever runs next in the process. It
    does not reproduce the same primary keys, which is why the returned ground truth, not the
    seed, is the record to score a run against.
    """
    random.seed(seed)
    rng = np.random.default_rng(seed)

    frames = generate_moth_series(
        num_frames=num_frames,
        num_moths=num_moths,
        num_transient_moths=num_transient_moths,
        min_frames_per_moth=min_frames_per_moth,
        beginning_timestamp=_session_start_timestamp(deployment),
        minutes_interval=minutes_interval,
        minutes_interval_variation=0,
        motion_scale=motion_scale,
        moth_size_range=TRACKING_MOTH_SIZE_RANGE,
        save_images=False,
    )
    _upload_frames(deployment, frames)

    # Group only after the dimensions are in place: grouping otherwise reads the first
    # image back out of object storage to fill them in, and the matching cost needs them.
    deployment.sync_captures(regroup_after=False)
    captures = _captures_for_frames(deployment, frames)
    SourceImage.objects.filter(pk__in=[c.pk for c in captures]).update(width=frames[0].width, height=frames[0].height)
    group_images_into_events(deployment)
    captures = _captures_for_frames(deployment, frames)

    algorithm, _ = Algorithm.objects.get_or_create(
        key=DEMO_CLASSIFIER_KEY, defaults=dict(name=DEMO_CLASSIFIER_NAME, task_type="classification")
    )
    store_features = with_features and pgvector_is_available()
    if with_features and not store_features:
        logger.warning(
            "The pgvector extension is not installed, so no feature embeddings will be generated. "
            "Track this session with require_features=False."
        )

    species = _species_taxa(deployment.project, taxa_list)
    identifiers = sorted({box.identifier for frame in frames for box in frame.bounding_boxes})
    taxon_by_insect = {identifier: species[i % len(species)] for i, identifier in enumerate(identifiers)}
    base_vector_by_insect = {identifier: rng.random(2048) for identifier in identifiers}

    insects = {
        identifier: SimulatedInsect(
            identifier=identifier,
            taxon_name=taxon_by_insect[identifier].name,
            frame_numbers=[],
            detection_ids=[],
        )
        for identifier in identifiers
    }

    for capture, frame in zip(captures, frames):
        for box in frame.bounding_boxes:
            occurrence = Occurrence.objects.create(
                event=capture.event,
                deployment=capture.deployment,
                project=capture.project,
            )
            detection = Detection.objects.create(
                source_image=capture,
                occurrence=occurrence,
                timestamp=capture.timestamp,
                bbox=list(box.bbox),
                frame_num=frame.frame_num,
            )
            features = None
            if store_features:
                features = (base_vector_by_insect[box.identifier] + rng.normal(0, 0.001, size=2048)).tolist()
            Classification.objects.create(
                detection=detection,
                taxon=taxon_by_insect[box.identifier],
                algorithm=algorithm,
                score=random.randint(65, 98) / 100,
                timestamp=capture.timestamp,
                terminal=True,
                features_2048=features,
            )
            occurrence.save()
            insects[box.identifier].frame_numbers.append(frame.frame_num)
            insects[box.identifier].detection_ids.append(detection.pk)
        capture.save()

    event = captures[0].event
    if event is None:
        raise RuntimeError("The generated captures were not grouped into an event.")
    capture_set = SourceImageCollection.objects.create(
        project=deployment.project,
        name=f"Tracking Demo Session {event.pk}",
        description="One night of closely-spaced captures with a known occurrence grouping.",
    )
    capture_set.images.set(captures)

    if create_crops:
        # Cropping fetches every capture back out of object storage, which is the slow part
        # of this fixture. Tests that only care about the grouping can skip it.
        create_detection_images(source_image_ids=[capture.pk for capture in captures])

    detection_count = sum(len(insect.detection_ids) for insect in insects.values())
    logger.info(
        f"Created tracking session: event {event.pk}, {len(captures)} captures, "
        f"{detection_count} detections, {len(insects)} simulated insects."
    )

    return TrackingSessionGroundTruth(
        project_id=deployment.project.pk,
        deployment_id=deployment.pk,
        event_id=event.pk,
        capture_set_id=capture_set.pk,
        seed=seed,
        capture_count=len(captures),
        detection_count=detection_count,
        feature_algorithm_key=algorithm.key if store_features else None,
        insects=[insects[identifier] for identifier in identifiers],
    )


def score_tracking_run(ground_truth: TrackingSessionGroundTruth) -> dict:
    """Compare the occurrences currently in the database against the ground truth.

    Returns the counts a tracking run should be judged on: how many simulated insects were
    rebuilt exactly, how many occurrences the event now holds, and the longest chain found.
    """
    event = Event.objects.get(pk=ground_truth.event_id)
    groups = [
        set(occurrence.detections.values_list("pk", flat=True))
        for occurrence in Occurrence.objects.filter(event=event)
    ]
    groups = [group for group in groups if group]
    truth = [set(insect.detection_ids) for insect in ground_truth.insects]
    exact = sum(1 for group in truth if group in groups)
    return {
        "simulated_insects": len(truth),
        "occurrences": len(groups),
        "exactly_recovered": exact,
        "longest_chain": max((len(group) for group in groups), default=0),
        "longest_true_chain": max((len(group) for group in truth), default=0),
    }
