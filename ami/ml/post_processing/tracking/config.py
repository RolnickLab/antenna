"""Settings for a tracking run: which sessions to track and how detections are matched.

This module uses pydantic only and has no Django imports, so it can be used and tested without a database.
"""

import pydantic

from ami.ml.results.schemas import reference

COST_NOTE = (
    "The default is a starting point that is still being tuned by experiment. "
    "It suits captures taken about 20 seconds apart."
)


class TrackingConfig(pydantic.BaseModel):
    """Scope and tunables for a tracking run.

    Scope: exactly one of ``source_image_collection_id`` or ``event_ids`` says
    which sessions to track. A capture set is the bulk path; an explicit event
    list is what the Events admin page sends.

    The matching cost between two detections in consecutive captures is
    ``iou_weight * (1 - IoU) + size_weight * (1 - size ratio) + distance_weight * (distance / diagonal)``.
    Two detections are linked only when the cost is below ``cost_threshold`` and
    every enabled limit passes. The field titles and descriptions are the help text
    shown on the admin form.
    """

    source_image_collection_id: int | None = reference(
        "capture_set",
        None,
        title="Capture set",
        description=(
            "Track the sessions that contain captures from this set. Every processed capture of those "
            "sessions is tracked, not only the captures in the set, because a chain needs the captures "
            "between its detections."
        ),
    )
    event_ids: list[int] = pydantic.Field([], title="Sessions")
    detection_algorithm_id: int | None = reference(
        "algorithm",
        None,
        title="Detector",
        description=(
            "Compare only the detections from this detection algorithm (its id). Leave blank to use the only detector "
            "in each session; a session with detections from more than one detector is then skipped, because "
            "two detectors find the same insect twice."
        ),
    )

    cost_threshold: float = pydantic.Field(
        1.0,
        title="Cost cutoff",
        ge=0,
        description=(
            "Two detections in neighbouring captures are only linked when their matching cost is below this "
            "value. The cost adds up how little the boxes overlap, how different their sizes are, and how far "
            "apart their centres are. Lower values link fewer detections and make fewer mistakes. " + COST_NOTE
        ),
    )
    iou_weight: float = pydantic.Field(
        1.0,
        title="Overlap weight",
        ge=0,
        description=("How strongly poor overlap between two boxes raises the cost. 0 ignores overlap. " + COST_NOTE),
    )
    size_weight: float = pydantic.Field(
        1.0,
        title="Size weight",
        ge=0,
        description=("How strongly a difference in box area raises the cost. 0 ignores size. " + COST_NOTE),
    )
    distance_weight: float = pydantic.Field(
        1.0,
        title="Distance weight",
        ge=0,
        description=(
            "How strongly the distance between box centres, measured as a share of the image diagonal, "
            "raises the cost. 0 ignores distance. " + COST_NOTE
        ),
    )

    min_iou: float | None = pydantic.Field(
        None,
        title="Minimum overlap",
        ge=0,
        le=1,
        description=(
            "Never link two detections whose boxes overlap by less than this (0 to 1, where 1 is identical "
            "boxes). Leave blank for no limit."
        ),
    )
    min_size_ratio: float | None = pydantic.Field(
        None,
        title="Minimum size ratio",
        ge=0,
        le=1,
        description=(
            "Never link two detections when the smaller box has less than this share of the area of the larger "
            "one (0 to 1). Leave blank for no limit."
        ),
    )
    max_distance: float | None = pydantic.Field(
        None,
        title="Maximum distance",
        ge=0,
        description=(
            "Never link two detections whose box centres are further apart than this share of the image "
            "diagonal (for example 0.1 is ten percent). Leave blank for no limit."
        ),
    )
    max_capture_interval_seconds: float | None = pydantic.Field(
        None,
        title="Maximum time between captures",
        gt=0,
        description=(
            "Never link detections in two neighbouring captures taken further apart than this many seconds. "
            "Leave blank for no limit."
        ),
    )

    skip_if_human_identifications: bool = pydantic.Field(
        True,
        title="Skip sessions with human identifications",
        description="Leave a session alone when someone has already identified one of its occurrences.",
    )
    require_fresh_event: bool = pydantic.Field(
        True,
        title="Only track sessions that have not been tracked",
        description=(
            "Skip a session when any of its detections is already linked to a next one. Turned off, a run "
            "adds links between detections that have none and merges the occurrences they join; it never "
            "removes or replaces a link, and never takes a detection out of its occurrence."
        ),
    )

    preview_only: bool = pydantic.Field(
        False,
        title="Preview only",
        description=(
            "Work out the links and merges and report how many there would be on the job, without changing "
            "anything."
        ),
    )

    @pydantic.root_validator(skip_on_failure=True)
    def _exactly_one_scope(cls, values: dict) -> dict:
        scopes = [values.get("source_image_collection_id"), values.get("event_ids") or None]
        if sum(s is not None for s in scopes) != 1:
            raise ValueError("Provide exactly one of source_image_collection_id or event_ids")
        return values

    class Config:
        extra = "forbid"
