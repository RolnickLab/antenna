"""Small synthetic capture sessions for tracking tests.

A session is described by the bounding boxes in each capture. Every box becomes a detection with its own
occurrence and a classification, which is the state a pipeline leaves behind before tracking runs.
"""
import datetime

from ami.main.models import Classification, Deployment, Detection, Occurrence, SourceImage, Taxon

IMAGE_SIZE = (1000, 1000)


def create_session(
    deployment: Deployment,
    boxes_per_capture: list[list[list[int]] | None],
    taxon: Taxon,
    start: datetime.datetime | None = None,
    interval_seconds: float = 20,
    score: float = 0.9,
) -> list[SourceImage]:
    """Create captures spaced ``interval_seconds`` apart and return them in time order.

    ``None`` leaves a capture unprocessed (no detection rows); an empty list gives it a null-bbox marker
    row, as a processed capture with no insects has. The deployment groups the captures into sessions.
    """
    start = start or datetime.datetime(2026, 7, 1, 22, 0, 0)
    captures: list[SourceImage] = []
    for i, boxes in enumerate(boxes_per_capture):
        timestamp = start + datetime.timedelta(seconds=i * interval_seconds)
        capture = SourceImage.objects.create(
            deployment=deployment,
            project=deployment.project,
            timestamp=timestamp,
            path=f"tracking/{timestamp:%Y%m%d%H%M%S}_{i}.jpg",
            width=IMAGE_SIZE[0],
            height=IMAGE_SIZE[1],
        )
        captures.append(capture)
    deployment.save(update_calculated_fields=True, regroup_async=False)
    for capture, boxes in zip(captures, boxes_per_capture):
        capture.refresh_from_db()
        if boxes is None:
            continue
        if not boxes:
            Detection.objects.create(source_image=capture, bbox=None, timestamp=capture.timestamp)
        for bbox in boxes:
            add_detection(capture, bbox, taxon, score)
    return captures


def add_detection(capture: SourceImage, bbox: list[int], taxon: Taxon, score: float = 0.9) -> Detection:
    """Add one detection with its own occurrence and a terminal classification."""
    occurrence = Occurrence.objects.create(event=capture.event, deployment=capture.deployment, project=capture.project)
    detection = Detection.objects.create(
        source_image=capture, occurrence=occurrence, bbox=bbox, timestamp=capture.timestamp
    )
    Classification.objects.create(
        detection=detection, taxon=taxon, score=score, timestamp=capture.timestamp, terminal=True
    )
    occurrence.save()
    return detection
