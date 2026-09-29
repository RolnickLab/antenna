class PipelineNotConfigured(ValueError):
    pass


class FeatureResultsMatchNoDetections(Exception):
    """A feature-only batch returned boxes, and none of them is a detection Antenna has.

    Nothing can be stored for such a batch, and the same detections would be sent again on
    every run, so the job fails instead of skipping it.
    """

    def __init__(self, message: str = "", unmatched: int = 0):
        super().__init__(message)
        self.unmatched = unmatched
