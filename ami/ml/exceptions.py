class PipelineNotConfigured(ValueError):
    pass


class FeatureResultsStoredNothing(Exception):
    """A feature-only batch stored no vector while its images still have detections without one.

    This happens when no returned box matches a stored detection, when the boxes come back
    without vectors, or when the service returns no boxes at all. The same detections would
    be sent again on every run, so the job fails instead of skipping the batch.
    """

    def __init__(self, message: str = "", unmatched: int = 0, without_vector: int = 0):
        super().__init__(message)
        self.unmatched = unmatched
        self.without_vector = without_vector
