"""Occurrence tracking: linking the detections of one insect across consecutive captures.

``config`` and ``matching`` are pure Python; ``task`` and ``sessions`` use the database.
"""

from .config import TrackingConfig
from .task import TrackingTask

__all__ = ["TrackingConfig", "TrackingTask"]
