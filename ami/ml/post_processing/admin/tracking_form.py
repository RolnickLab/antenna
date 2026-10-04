from __future__ import annotations

from ami.ml.post_processing.admin.forms import SchemaActionForm
from ami.ml.post_processing.tracking_task import TrackingConfig


class TrackingActionForm(SchemaActionForm):
    """Knobs surfaced when an admin triggers Occurrence tracking.

    Every field is generated from ``TrackingConfig``; the scope (capture set or sessions) is supplied
    by the admin entry point.
    """

    schema = TrackingConfig
    exclude_fields = ("source_image_collection_id", "event_ids")
